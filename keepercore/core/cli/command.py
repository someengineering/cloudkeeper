import json
from abc import abstractmethod, ABC
from functools import partial
from typing import List, Optional, Any, Tuple, AsyncGenerator, Union, Hashable, Iterable

from aiostream import stream
from aiostream.aiter_utils import is_async_iterable
from aiostream.core import Stream

from core.cli.cli import CLISource, CLISink, Sink, Source, CLICommand, Flow, CLIDependencies, CLIPart, key_values_parser
from core.db.model import QueryModel
from core.error import CLIParseError
from core.query.query_parser import parse_query
from core.types import Json, JsonElement


class EchoSource(CLISource):  # type: ignore
    """
    Usage: echo <json>

    The defined json will be parsed and written to the out stream.
    If the defined element is a json array, each element will be send downstream.

    Example:
        echo "test"              # will result in ["test"]
        echo [1,2,3,4] | count   # will result in [{ "matched": 4, "not_matched": 0 }]
    """

    @property
    def name(self) -> str:
        return "echo"

    async def parse(self, arg: Optional[str] = None, **env: str) -> Source:
        js = json.loads(arg if arg else "")
        if isinstance(js, list):
            elements = js
        elif isinstance(js, (str, int, float, bool, dict)):
            elements = [js]
        else:
            raise AttributeError(f"Echo does not understand {arg}.")

        for element in elements:
            yield element


class MatchSource(CLISource):  # type: ignore
    """
    Usage: match <query>

    A query is performed against the graph database and all resulting elements will be emitted.
    To learn more about the query, visit todo: link is missing.

    Example:
        match isinstance("ec2") and (cpu>12 or cpu<3)  # will result in all matching elements [{..}, {..}, .. {..}]

    Environment Variables:
        graph [mandatory]: the name of the graph to operate on
        section [optional, defaults to "reported"]: on which section the query is performed
    """

    @property
    def name(self) -> str:
        return "match"

    async def parse(self, arg: Optional[str] = None, **env: str) -> Source:
        # db name and section is coming from the env
        graph_name = env["graph"]
        query_section = env.get("section", "reported")
        if not arg:
            raise CLIParseError("match command needs a query to execute, but nothing was given!")
        query = parse_query(arg)
        model = await self.dependencies.model_handler.load_model()
        db = self.dependencies.db_access.get_graph_db(graph_name)
        return db.query_list(QueryModel(query, model, query_section), with_system_props=True)


class EnvSource(CLISource):  # type: ignore
    """
    Usage: env

    Emits the provided environment.
    This is useful to inspect the environment given to the CLI interpreter.

    Example:
        env  # will result in a json object representing the env. E.g.: [{ "env_var1": "test", "env_var2": "foo" }]
    """

    @property
    def name(self) -> str:
        return "env"

    async def parse(self, arg: Optional[str] = None, **env: str) -> Source:
        return stream.just(env)


class CountCommand(CLICommand):  # type: ignore
    """
    Usage: count [arg]

    In case no arg is given: it counts the number of instances provided to count.
    In case of arg: it pulls the property with the name of arg, translates it to a number and sums it.

    Parameter:
        arg [optional]: Instead of counting the instances, sum the property of all objects with this name.

    Example:
        echo [{"a": 1}, {"a": 2}, {"a": 3}] | count    # will result in [{ "matched": 3, "not_matched": 0 }]
        echo [{"a": 1}, {"a": 2}, {"a": 3}] | count a  # will result in [{ "matched": 6, "not_matched": 0 }]
        echo [{"a": 1}, {"a": 2}, {"a": 3}] | count b  # will result in [{ "matched": 0, "not_matched": 3 }]
    """

    @property
    def name(self) -> str:
        return "count"

    async def parse(self, arg: Optional[str] = None, **env: str) -> Flow:
        def inc_prop(o: Any) -> Tuple[int, int]:
            def prop_value() -> Tuple[int, int]:
                try:
                    return int(o[arg]), 0
                except Exception:
                    return 0, 1

            return prop_value() if arg in o else (0, 1)

        def inc_identity(_: Any) -> Tuple[int, int]:
            return 1, 0

        fn = inc_prop if arg else inc_identity

        async def count_in_stream(content: Stream) -> AsyncGenerator[JsonElement, None]:
            counter = 0
            no_match = 0

            async with content.stream() as in_stream:
                async for element in in_stream:
                    cnt, not_matched = fn(element)
                    counter += cnt
                    no_match += not_matched
            yield {"matched": counter, "not_matched": no_match}

        return count_in_stream


class ChunkCommand(CLICommand):  # type: ignore
    """
    Usage: chunk [num]

    Take <num> number of elements from the input stream, put them in a list and send a stream of list downstream.
    The last chunk might have a lower size than the defined chunk size.

    Parameter:
        num [optional, defaults to 100]: the number of elements to put into a chunk.

    Example:
         echo [1,2,3,4,5] | chunk 2  # will result in [[1, 2], [3, 4], [5]]
         echo [1,2,3,4,5] | chunk    # will result in [[1, 2, 3, 4, 5]]

    See:
        flatten for the reverse operation.
    """

    @property
    def name(self) -> str:
        return "chunk"

    async def parse(self, arg: Optional[str] = None, **env: str) -> Flow:
        size = int(arg) if arg else 100
        return lambda in_stream: stream.chunks(in_stream, size)


class FlattenCommand(CLICommand):  # type: ignore
    """
    Usage: flatten

    Take array elements from the input stream and put them to the output stream one after the other,
    while preserving the original order.

    Example:
         echo [1, 2, 3, 4, 5] | chunk 2 | flatten  # will result in [1, 2, 3, 4, 5]
         echo [1, 2, 3, 4, 5] | flatten            # nothing to flat [1, 2, 3, 4, 5]
         echo [[1, 2], 3, [4, 5]] | flatten        # will result in [1, 2, 3, 4, 5]

    See:
        chunk which is able to put incoming elements into chunks
    """

    @property
    def name(self) -> str:
        return "flatten"

    async def parse(self, arg: Optional[str] = None, **env: str) -> Flow:
        def iterate(it: Any) -> Stream:
            return stream.iterate(it) if is_async_iterable(it) or isinstance(it, Iterable) else stream.just(it)

        return lambda in_stream: stream.flatmap(in_stream, iterate)


class UniqCommand(CLICommand):  # type: ignore
    """
    Usage: uniq

    All elements flowing through the uniq command are analyzed and all duplicates get removed.
    Note: a hash value is computed from json objects, which is ignorant of the order of properties,
    so that {"a": 1, "b": 2} is declared equal to {"b": 2, "a": 1}

    Example:
        echo [1, 2, 3, 1, 2, 3] | uniq                     # will result in [1, 2, 3]
        echo [{"a": 1, "b": 2}, {"b": 2, "a": 1}] | uniq   # will result in [{"a": 1, "b": 2}]
    """

    @property
    def name(self) -> str:
        return "uniq"

    async def parse(self, arg: Optional[str] = None, **env: str) -> Flow:
        visited = set()

        def hashed(item: Any) -> Hashable:
            if isinstance(item, dict):
                return json.dumps(item, sort_keys=True)
            else:
                raise CLIParseError(f"{self.name} can not make {item}:{type(item)} uniq")

        def has_not_seen(item: Any) -> bool:
            item = item if isinstance(item, Hashable) else hashed(item)

            if item in visited:
                return False
            else:
                visited.add(item)
                return True

        return lambda in_stream: stream.filter(in_stream, has_not_seen)


class SetDesiredState(CLICommand, ABC):  # type: ignore
    @abstractmethod
    def patch(self, arg: Optional[str] = None, **env: str) -> Json:
        # deriving classes need to define how to patch
        pass

    async def parse(self, arg: Optional[str] = None, **env: str) -> Flow:
        buffer_size = 1000
        result_section = env["result_section"].split(",") if "result_section" in env else ["reported", "desired"]
        func = partial(self.set_desired, env["graph"], self.patch(arg, **env), result_section)
        return lambda in_stream: stream.flatmap(stream.chunks(in_stream, buffer_size), func)

    async def set_desired(
        self, graph_name: str, patch: Json, result_section: Union[str, List[str]], items: List[Json]
    ) -> AsyncGenerator[JsonElement, None]:
        db = self.dependencies.db_access.get_graph_db(graph_name)
        node_ids = []
        for item in items:
            if "_id" in item:
                node_ids.append(item["_id"])
            elif isinstance(item, str):
                node_ids.append(item)
        async for update in db.update_nodes_desired(patch, node_ids, result_section, with_system_props=True):
            yield update


class DesireCommand(SetDesiredState):
    """
    Usage: desire [property]=[value]

    Set one or more desired properties for every database node that is received on the input channel.
    The desired state of each node in the database is merged with this new desired state, so that
    existing desired state not defined in this command is not touched.

    This command assumes, that all incoming elements are either objects coming from a query or are object ids.
    All objects coming from a query will have a property `_id`.

    The result of this command will emit the complete object with desired and reported state:
    { "_id": "..", "desired": { .. }, "reported": { .. } }

    Parameter:
       One or more parameters of form [property]=[value] separated by a space.
       [property] is the name of the property to set.
       [value] is a json primitive type: string, int, number, boolean or null.
       Quotation marks for strings are optional.


    Example:
        match isinstance("ec2") | desire a=b b="c" num=2   # will result in
            [
                { "_id": "abc" "desired": { "a": "b", "b: "c" "num": 2, "other": "abc" }, "reported": { .. } },
                .
                .
                { "_id": "xyz" "desired": { "a": "b", "b: "c" "num": 2 }, "reported": { .. } },
            ]
        echo [{"_id": "id1"}, {"_id": "id2"}] | desire a=b
            [
                { "_id": "id1", "desired": { "a": b }, "reported": { .. } },
                { "_id": "id2", "desired": { "a": b }, "reported": { .. } },
            ]
        echo ["id1", "id2"] | desire a=b
            [
                { "_id": "id1", "desired": { "a": b }, "reported": { .. } },
                { "_id": "id2", "desired": { "a": b }, "reported": { .. } },
            ]
    """

    @property
    def name(self) -> str:
        return "desire"

    def patch(self, arg: Optional[str] = None, **env: str) -> Json:
        if arg and arg.strip():
            return key_values_parser.parse(arg)  # type: ignore
        else:
            return {}


class MarkDeleteCommand(SetDesiredState):
    """
    Usage: mark_delete

    Mark incoming objects for deletion.
    All objects marked as such will be finally deleted in the next delete run.

    This command assumes, that all incoming elements are either objects coming from a query or are object ids.
    All objects coming from a query will have a property `_id`.

    The result of this command will emit the complete object with desired and reported state:
    { "_id": "..", "desired": { .. }, "reported": { .. } }

    Example:
        match isinstance("ec2") and atime<"-2d" | mark_delete
            [
                { "_id": "abc" "desired": { "delete": true }, "reported": { .. } },
                .
                .
                { "_id": "xyz" "desired": { "delete": true }, "reported": { .. } },
            ]
        echo [{"_id": "id1"}, {"_id": "id2"}] | mark_delete
            [
                { "_id": "id1", "desired": { "delete": true }, "reported": { .. } },
                { "_id": "id2", "desired": { "delete": true }, "reported": { .. } },
            ]
        echo ["id1", "id2"] | mark_delete
            [
                { "_id": "id1", "desired": { "delete": true }, "reported": { .. } },
                { "_id": "id2", "desired": { "delete": true }, "reported": { .. } },
            ]
    """

    @property
    def name(self) -> str:
        return "mark_delete"

    def patch(self, arg: Optional[str] = None, **env: str) -> Json:
        return {"delete": True}


class ListSink(CLISink):  # type: ignore
    @property
    def name(self) -> str:
        return "out"

    async def parse(self, arg: Optional[str] = None, **env: str) -> Sink[List[JsonElement]]:
        return lambda in_stream: stream.list(in_stream)


def all_sources(d: CLIDependencies) -> List[CLISource]:
    return [EchoSource(d), EnvSource(d), MatchSource(d)]


def all_sinks(d: CLIDependencies) -> List[CLISink]:
    return [ListSink(d)]


def all_commands(d: CLIDependencies) -> List[CLICommand]:
    return [ChunkCommand(d), FlattenCommand(d), CountCommand(d), DesireCommand(d), MarkDeleteCommand(d), UniqCommand(d)]


def all_parts(d: CLIDependencies) -> List[CLIPart]:
    # noinspection PyTypeChecker
    return all_sources(d) + all_commands(d) + all_sinks(d)
