import cloudkeeper.logging
from dataclasses import dataclass
from typing import Optional, ClassVar
from cloudkeeper.graph import Graph
from cloudkeeper.baseresources import (
    BaseAccount,
    BaseRegion,
    BaseInstance,
    BaseNetwork,
    InstanceStatus,
)

log = cloudkeeper.logging.getLogger("cloudkeeper." + __name__)


@dataclass(eq=False)
class OnpremLocation(BaseAccount):
    resource_type: ClassVar[str] = "onprem_location"

    def delete(self, graph: Graph) -> bool:
        return NotImplemented


@dataclass(eq=False)
class OnpremRegion(BaseRegion):
    resource_type: ClassVar[str] = "onprem_region"

    def delete(self, graph: Graph) -> bool:
        return NotImplemented


@dataclass(eq=False)
class OnpremResource:
    def delete(self, graph: Graph) -> bool:
        log.debug(
            f"Deleting resource {self.id} in account {self.account(graph).id} region {self.region(graph).id}"
        )
        return True

    def update_tag(self, key, value) -> bool:
        log.debug(f"Updating or setting tag {key}: {value} on resource {self.id}")
        return True

    def delete_tag(self, key) -> bool:
        log.debug(f"Deleting tag {key} on resource {self.id}")
        return True


@dataclass(eq=False)
class OnpremInstance(OnpremResource, BaseInstance):
    resource_type: ClassVar[str] = "onprem_instance"
    network_device: Optional[str] = None
    network_ip4: Optional[str] = None
    network_ip6: Optional[str] = None

    instance_status_map = {
        "running": InstanceStatus.RUNNING,
    }

    def _instance_status_setter(self, value: str) -> None:
        self._instance_status = self.instance_status_map.get(
            value, InstanceStatus.UNKNOWN
        )


OnpremInstance.instance_status = property(
    OnpremInstance._instance_status_getter, OnpremInstance._instance_status_setter
)


@dataclass(eq=False)
class OnpremNetwork(OnpremResource, BaseNetwork):
    resource_type: ClassVar[str] = "onprem_network"
