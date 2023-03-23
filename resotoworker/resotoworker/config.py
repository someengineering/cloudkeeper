import concurrent.futures
from collections import namedtuple
from resotolib.graph import GraphMergeKind
from resotolib.config import Config
from resotolib.proc import num_default_threads
from resotolib.baseplugin import BaseCollectorPlugin
from resotolib.logger import log
from attrs import define, field
from typing import ClassVar, Optional, List, Type


_collector_plugins: List[Type[BaseCollectorPlugin]] = []
PluginAutoEnabledResult = namedtuple("PluginAutoEnabledResult", ["cloud", "auto_enabled"])


def add_config(config: Config, collector_plugins: List[Type[BaseCollectorPlugin]]) -> None:
    global _collector_plugins
    _collector_plugins = collector_plugins
    config.add_config(ResotoWorkerConfig)


def get_default_collectors() -> List[str]:
    def plugin_auto_enabled(plugin: Type[BaseCollectorPlugin]) -> PluginAutoEnabledResult:
        return PluginAutoEnabledResult(plugin.cloud, plugin.auto_enabled())

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=20, thread_name_prefix="AutoDiscovery") as executor:
            return [
                plugin_result.cloud
                for plugin_result in executor.map(plugin_auto_enabled, _collector_plugins, timeout=10)
                if plugin_result.auto_enabled
            ]
    except concurrent.futures.TimeoutError:
        log.error("Timeout while getting auto-enabled collectors")
    except Exception as e:
        log.error(f"Unhandled exception while getting auto-enabled collectors: {e}")
    return []


@define
class ResotoWorkerConfig:
    kind: ClassVar[str] = "resotoworker"
    collector: List[str] = field(
        factory=get_default_collectors,
        metadata={"description": "List of collectors to run", "restart_required": True},
    )
    graph: str = field(
        default="resoto",
        metadata={"description": "Name of the graph to import data into and run searches on"},
    )
    timeout: int = field(default=10800, metadata={"description": "Collection/cleanup timeout in seconds"})
    pool_size: int = field(default=5, metadata={"description": "Collector thread/process pool size"})
    fork_process: bool = field(default=True, metadata={"description": "Use forked process instead of threads"})
    graph_merge_kind: GraphMergeKind = field(
        default=GraphMergeKind.cloud,
        metadata={"description": "Resource kind to merge graph at (cloud or account)"},
    )
    debug_dump_json: bool = field(default=False, metadata={"description": "Dump the generated JSON data to disk"})
    tempdir: Optional[str] = field(default=None, metadata={"description": "Directory to create temporary files in"})
    cleanup: bool = field(default=False, metadata={"description": "Enable cleanup of resources"})
    cleanup_pool_size: int = field(
        factory=lambda: num_default_threads() * 2,
        metadata={"description": "How many cleanup threads to run in parallel"},
    )
    cleanup_dry_run: bool = field(
        default=True,
        metadata={"description": "Do not actually cleanup resources, just create log messages"},
    )
    no_tls: bool = field(
        default=False,
        metadata={
            "description": "Disable TLS for the web server, even if Resoto Core uses TLS.",
            "restart_required": True,
        },
    )
    web_host: str = field(
        default="::",
        metadata={
            "description": "IP address to bind the web server to",
            "restart_required": True,
        },
    )
    web_port: int = field(
        default=9956,
        metadata={
            "description": "Web server tcp port to listen on",
            "restart_required": True,
        },
    )
    web_path: str = field(
        default="/",
        metadata={
            "description": "Web root in browser (change if running behind an ingress proxy)",
            "restart_required": True,
        },
    )
