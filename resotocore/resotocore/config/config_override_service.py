from typing import List, Optional, Callable, Dict, Any, Awaitable, cast
from pathlib import Path
import yaml
import logging
import asyncio
from resotocore.types import Json
from resotocore.ids import ConfigId
from resotocore.util import merge_json_elements
from resotocore.config import ConfigOverride
from resotocore.async_extensions import run_async
from deepdiff import DeepDiff
import aiofiles.os as aos

log = logging.getLogger("config_override_service")


class ConfigOverrideService(ConfigOverride):
    def __init__(self, override_paths: List[Path], sleep_time: float = 3.0):
        self.override_paths = override_paths
        self.sleep_time = sleep_time
        self.overrides: Dict[ConfigId, Json] = {}
        self.stop_watcher = asyncio.Event()
        self.override_change_hooks: List[Callable[[Dict[ConfigId, Json]], Awaitable[Any]]] = []
        self.watcher_task: Optional[asyncio.Task[Any]] = None
        self.overrides = self._load_overrides()
        self.mtime_hash: int = 0

    def add_override_change_hook(self, hook: Callable[[Dict[ConfigId, Json]], Awaitable[Any]]) -> None:
        self.override_change_hooks.append(hook)

    # no async here because page cache will keep this in memory anyway
    def _load_overrides(self, silent: bool = False) -> Dict[ConfigId, Json]:
        if not self.override_paths:
            return {}

        # all config files that will be used
        config_files: List[Path] = []
        # collect them all
        for path in self.override_paths:
            if path.is_dir():
                config_files.extend(
                    [file for file in path.iterdir() if file.is_file() and file.suffix in (".yml", ".yaml")]
                )
            else:
                config_files.append(path)

        # json with all merged overrides for all components such as resotocore, resotoworker, etc.
        overrides_json: Json = {}
        # merge all provided overrides into a single object, preferring the values from the last override
        for config_file in config_files:
            with config_file.open() as f:
                try:
                    raw_yaml = yaml.safe_load(f)
                    with_config_id = {config_file.stem: raw_yaml}
                    merged = merge_json_elements(overrides_json, with_config_id)
                    overrides_json = cast(Json, merged)
                except Exception as e:
                    log.warning(f"Can't read the config override {config_file}, skipping. Reason: {e}")

        def is_dict(config_id: str, obj: Any) -> bool:
            if not isinstance(obj, dict):
                if not silent:
                    log.warning(f"Config override with id {config_id} contains invalid data, skipping.")
                return False
            return True

        # dict with all overrides for all config ids, such as resoto.core, resoto.worker, etc.
        all_config_overrides: Dict[ConfigId, Json] = {
            ConfigId(k): v for k, v in overrides_json.items() if is_dict(k, v)
        }

        if all_config_overrides is None:
            if not silent:
                log.warning("No config overrides found.")
            return {}

        return all_config_overrides

    def get_override(self, config_id: ConfigId) -> Optional[Json]:
        return self.overrides.get(config_id)

    def get_all_overrides(self) -> Dict[ConfigId, Json]:
        return self.overrides

    def watch_for_changes(self) -> None:
        async def watcher() -> None:
            while not self.stop_watcher.is_set():
                # all config files that needs to be checked for changes
                config_files: List[Path] = []
                # do a flatmap on directories
                for path in self.override_paths:
                    if await aos.path.isdir(path):
                        config_files.extend(
                            [
                                Path(entry.path)
                                for entry in await aos.scandir(path)  # scandir avoids extra syscalls
                                if entry.is_file() and Path(entry.path).suffix in (".yml", ".yaml")
                            ]
                        )
                    else:
                        config_files.append(path)

                # a quick optimization to avoid reading the files if none has been changed
                mtime_hash = 0
                config_files = sorted(config_files)
                for file in config_files:
                    mtime_hash = hash((mtime_hash, (await aos.stat(file)).st_mtime))

                if mtime_hash == self.mtime_hash:
                    await asyncio.sleep(self.sleep_time)
                    continue
                self.mtime_hash = mtime_hash

                overrides = await run_async(lambda: self._load_overrides(silent=True))
                diff = DeepDiff(self.overrides, overrides, ignore_order=True)

                if diff:
                    self.overrides = overrides
                    for hook in self.override_change_hooks:
                        await hook(self.overrides)

                await asyncio.sleep(self.sleep_time)

        # watcher is already running
        if self.watcher_task:
            return

        self.stop_watcher.clear()
        self.watcher_task = asyncio.create_task(watcher())

    def stop(self) -> None:
        self.stop_watcher.set()
        self.watcher_task = None
