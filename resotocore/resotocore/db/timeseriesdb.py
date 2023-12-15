import logging
import time
from datetime import timedelta, datetime, timezone
from functools import partial
from typing import Optional, List, Set, Union, cast, Dict, Callable

from attr import evolve, define
from resotocore.core_config import CoreConfig
from resotocore.db import arango_query
from resotocore.db.async_arangodb import AsyncArangoDB, AsyncCursor, AsyncArangoTransactionDB
from resotocore.db.graphdb import GraphDB
from resotocore.db.model import QueryModel
from resotocore.query.model import Predicate
from resotocore.types import Json, JsonElement
from resotocore.util import utc_str, utc, if_set, parse_utc
from resotolib.durations import duration_str

log = logging.getLogger(__name__)


@define
class TimeSeriesBucket:
    start: timedelta
    end: timedelta
    resolution: timedelta

    def __str__(self) -> str:
        return (
            f"Bucket(start={duration_str(self.start)}, "
            f"end={duration_str(self.end)}, resolution={duration_str(self.resolution)})"
        )


class TimeSeriesDB:
    def __init__(self, db: AsyncArangoDB, collection_name: str, config: CoreConfig) -> None:
        self.db = db
        self.collection_name = collection_name
        self.meta_db = f"{collection_name}_meta"
        self.names_db = f"{collection_name}_names"
        self.config = config
        self.buckets = self._buckets()
        self.smallest_resolution = min(bucket.resolution for bucket in self.buckets)

    async def __execute_aql(
        self, query: str, bind_vars: Optional[Json] = None, tx: Optional[AsyncArangoTransactionDB] = None
    ) -> List[JsonElement]:
        async with await (tx or self.db).aql_cursor(query, bind_vars=bind_vars) as crsr:
            return [el async for el in crsr]

    async def add_entries(self, name: str, query_model: QueryModel, graph_db: GraphDB, at: Optional[int] = None) -> int:
        query = query_model.query
        model = query_model.model
        assert query.aggregate is not None, "Only aggregate queries are supported for time series."
        assert len(query.aggregate.group_func) == 1, "Only a single group function is supported for time series."
        # make sure the final value is called "v"
        query = evolve(
            query,
            aggregate=evolve(query.aggregate, group_func=[evolve(query.aggregate.group_func[0], as_name="v")]),
        )
        at = at if at is not None else int(time.time())  # only use seconds
        qs, bv = arango_query.create_time_series(QueryModel(query, model), graph_db, self.collection_name, name, at)
        result, *_ = cast(List[int], await self.__execute_aql(qs, bv))
        if result > 0:
            # update meta information
            await self.__execute_aql(
                "UPSERT { _key: @key } "
                "INSERT { _key: @key, created_at: DATE_NOW(), last_updated: DATE_NOW(), count: @count } "
                f"UPDATE {{ last_updated: DATE_NOW(), count: @count }} IN `{self.names_db}`",
                dict(key=name, count=result),
            )

        return result

    async def load_time_series(
        self,
        name: str,
        start: datetime,
        end: datetime,
        *,
        group_by: Optional[Set[str]] = None,
        filter_by: Optional[List[Predicate]] = None,
        granularity: Optional[Union[timedelta, int]] = None,
        trafo: Optional[Callable[[Json], Json]] = None,
    ) -> AsyncCursor:
        """
        Load time series data.
        :param name: The name of the time series.
        :param start: Filter data after this time.
        :param end: Filter data before this time.
        :param group_by: Combine defined group properties. Only existing group properties can be used.
        :param filter_by: Filter specific group properties by predicate.
        :param granularity: Optional timedelta to retrieve data in a specific granularity.
               The minimum granularity is one hour.
               In case this number is an integer, it is interpreted as the number of steps between start and end.
        :param trafo: Optional transformation function to apply to each result.
        :return: A cursor to iterate over the time series data.
        """
        assert start < end, "start must be before end"
        assert name, "name must not be empty"
        duration = end - start

        # compute effective granularity
        if isinstance(granularity, int):
            grl = duration / granularity
        elif isinstance(granularity, timedelta):
            grl = granularity
        else:
            grl = duration / 20  # default to 20 datapoints if nothing is specified
        if grl < timedelta(hours=1):
            grl = timedelta(hours=1)

        qs, bv = arango_query.load_time_series(self.collection_name, name, start, end, grl, group_by, filter_by)

        def result_trafo(js: Json) -> Json:
            js["at"] = utc_str(datetime.fromtimestamp(js["at"], timezone.utc))
            return js

        async with await self.db.aql_cursor(qs, bind_vars=bv, trafo=trafo or result_trafo) as crsr:
            return crsr

    async def compact_time_series(self, now: Optional[datetime] = None) -> None:
        def ts_format(ts: str, js: Json) -> Json:
            js["ts"] = ts
            js["at"] = int(js["at"])
            return js

        now = now or utc()
        # check if there is something to do
        one_year_ago = now - timedelta(days=365)
        last_run = if_set(
            await self.db.get(self.meta_db, "last_run"),
            lambda d: parse_utc(d["last_run"]),
            one_year_ago,
        )
        if (now - last_run) < self.smallest_resolution:
            return  # nothing to compact
        all_ts = cast(List[Json], await self.__execute_aql(f"FOR d IN {self.names_db} return d"))
        times: Dict[str, datetime] = {
            e["_key"]: datetime.fromtimestamp(e["last_updated"] / 1000.0, timezone.utc) for e in all_ts
        }
        # acquire a lock and make sure, we are the only ones that enter this
        try:
            ttl = int((now + timedelta(minutes=15)).timestamp())
            await self.db.insert(self.meta_db, dict(_key="lock", expires=ttl))
        except Exception:
            return  # lock already exists
        # do the work while being sure to be the only one
        try:
            for ts, last_updated in times.items():
                for bucket in self.buckets:
                    c_start = max(now - bucket.end, last_run - bucket.start)
                    c_end = now - bucket.start
                    if c_end <= c_start or (c_end - c_start) < bucket.resolution or last_updated < c_start:
                        continue  # safeguard
                    if ts_data := [
                        e
                        async for e in await self.load_time_series(
                            ts, c_start, c_end, granularity=bucket.resolution, trafo=partial(ts_format, ts)
                        )
                    ]:
                        log.info(f"Compacting {ts} in bucket {bucket} to {len(ts_data)} entries.")
                        async with self.db.begin_transaction(write=self.collection_name) as tx:
                            await self.__execute_aql(
                                "FOR a in @@coll FILTER a.at>=@start and a.at<=@end REMOVE a IN @@coll",
                                {"start": c_start.timestamp(), "end": c_end.timestamp(), "@coll": self.collection_name},
                                tx=tx,
                            )
                            await tx.insert_many(self.collection_name, ts_data)
            # update last run
            await self.db.insert(self.meta_db, dict(_key="last_run", last_run=utc_str(now)), overwrite=True)
        finally:
            await self.db.delete(self.meta_db, "lock", ignore_missing=True)

    async def create_update_schema(self) -> None:
        if not await self.db.has_collection(self.collection_name):
            await self.db.create_collection(self.collection_name)
        collection = self.db.collection(self.collection_name)
        indexes = {idx["name"]: idx for idx in cast(List[Json], collection.indexes())}
        if "ttl" in indexes:
            collection.delete_index("ttl")
        if "access" not in indexes:
            collection.add_persistent_index(["ts", "at"], name="access")
        if not await self.db.has_collection(self.meta_db):
            await self.db.create_collection(self.meta_db)
        # meta collection: store information to handle ts
        collection = self.db.collection(self.meta_db)
        indexes = {idx["name"]: idx for idx in cast(List[Json], collection.indexes())}
        if "ttl" not in indexes:
            collection.add_ttl_index(["expires"], expiry_time=int(timedelta(hours=3).total_seconds()), name="ttl")
        # names collection: store all names of time series
        if not await self.db.has_collection(self.names_db):
            await self.db.create_collection(self.names_db)

    async def wipe(self) -> bool:
        return (
            await self.db.truncate(self.collection_name)
            and await self.db.truncate(self.names_db)
            and await self.db.truncate(self.meta_db)
        )

    def _buckets(self) -> List[TimeSeriesBucket]:
        result: List[TimeSeriesBucket] = []
        if bs := self.config.db.time_series_buckets:
            cfg = sorted(bs, key=lambda b: b.start)
            for a, z in zip(cfg, cfg[1:] + [None]):
                end = z.start if z else timedelta(days=730)
                result.append(TimeSeriesBucket(a.start, end, a.resolution))
        return result
