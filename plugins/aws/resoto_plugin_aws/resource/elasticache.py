from typing import ClassVar, Dict, Optional, List

from attrs import define, field

from resoto_plugin_aws.resource.base import AwsResource, AwsApiSpec
from resotolib.json_bender import Bender, S, Bend, ForallBend, K, F
from resoto_plugin_aws.aws_client import AwsClient
from resoto_plugin_aws.utils import ToDict
from typing import Tuple, Type
from datetime import datetime
from resotolib.types import Json
from resotolib.baseresources import BaseSnapshot
from resoto_plugin_aws.resource.ec2 import AwsEc2Vpc, AwsEc2SecurityGroup, AwsEc2Subnet
from resoto_plugin_aws.resource.iam import AwsIamRole


class ElastiCacheTaggable:
    def update_resource_tag(self, client: AwsClient, key: str, value: str) -> bool:
        if isinstance(self, AwsResource):
            client.call(
                service="elasticache",
                action="add_tags_to_resource",
                result_name=None,
                ResourceName=self.arn,
                Tags=[{"Key": key, "Value": value}],
            )
            return True
        return False

    def delete_resource_tag(self, client: AwsClient, key: str) -> bool:
        if isinstance(self, AwsResource):
            client.call(
                service="elasticache",
                action="remove_tags_from_resource",
                result_name=None,
                ResourceName=self.arn,
                TagKeys=[key],
            )
            return True
        return False


@define(eq=False, slots=False)
class AwsElastiCacheEndpoint:
    kind: ClassVar[str] = "aws_elasti_cache_endpoint"
    mapping: ClassVar[Dict[str, Bender]] = {"address": S("Address"), "port": S("Port")}
    address: Optional[str] = field(default=None)
    port: Optional[int] = field(default=None)


@define(eq=False, slots=False)
class AwsElastiCacheDestinationDetails:
    kind: ClassVar[str] = "aws_elasti_cache_destination_details"
    mapping: ClassVar[Dict[str, Bender]] = {
        "cloud_watch_logs_details": S("CloudWatchLogsDetails", "LogGroup"),
        "kinesis_firehose_details": S("KinesisFirehoseDetails", "DeliveryStream"),
    }
    cloud_watch_logs_details: Optional[str] = field(default=None)
    kinesis_firehose_details: Optional[str] = field(default=None)


@define(eq=False, slots=False)
class AwsElastiCachePendingLogDeliveryConfiguration:
    kind: ClassVar[str] = "aws_elasti_cache_pending_log_delivery_configuration"
    mapping: ClassVar[Dict[str, Bender]] = {
        "log_type": S("LogType"),
        "destination_type": S("DestinationType"),
        "destination_details": S("DestinationDetails") >> Bend(AwsElastiCacheDestinationDetails.mapping),
        "log_format": S("LogFormat"),
    }
    log_type: Optional[str] = field(default=None)
    destination_type: Optional[str] = field(default=None)
    destination_details: Optional[AwsElastiCacheDestinationDetails] = field(default=None)
    log_format: Optional[str] = field(default=None)


@define(eq=False, slots=False)
class AwsElastiCachePendingModifiedValues:
    kind: ClassVar[str] = "aws_elasti_cache_pending_modified_values"
    mapping: ClassVar[Dict[str, Bender]] = {
        "num_cache_nodes": S("NumCacheNodes"),
        "cache_node_ids_to_remove": S("CacheNodeIdsToRemove", default=[]),
        "engine_version": S("EngineVersion"),
        "cache_node_type": S("CacheNodeType"),
        "auth_token_status": S("AuthTokenStatus"),
        "log_delivery_configurations": S("LogDeliveryConfigurations", default=[])
        >> ForallBend(AwsElastiCachePendingLogDeliveryConfiguration.mapping),
    }
    num_cache_nodes: Optional[int] = field(default=None)
    cache_node_ids_to_remove: List[str] = field(factory=list)
    engine_version: Optional[str] = field(default=None)
    cache_node_type: Optional[str] = field(default=None)
    auth_token_status: Optional[str] = field(default=None)
    log_delivery_configurations: List[AwsElastiCachePendingLogDeliveryConfiguration] = field(factory=list)


@define(eq=False, slots=False)
class AwsElastiCacheNotificationConfiguration:
    kind: ClassVar[str] = "aws_elasti_cache_notification_configuration"
    mapping: ClassVar[Dict[str, Bender]] = {"topic_arn": S("TopicArn"), "topic_status": S("TopicStatus")}
    topic_arn: Optional[str] = field(default=None)
    topic_status: Optional[str] = field(default=None)


@define(eq=False, slots=False)
class AwsElastiCacheCacheSecurityGroupMembership:
    kind: ClassVar[str] = "aws_elasti_cache_cache_security_group_membership"
    mapping: ClassVar[Dict[str, Bender]] = {
        "cache_security_group_name": S("CacheSecurityGroupName"),
        "status": S("Status"),
    }
    cache_security_group_name: Optional[str] = field(default=None)
    status: Optional[str] = field(default=None)


@define(eq=False, slots=False)
class AwsElastiCacheCacheParameterGroupStatus:
    kind: ClassVar[str] = "aws_elasti_cache_cache_parameter_group_status"
    mapping: ClassVar[Dict[str, Bender]] = {
        "cache_parameter_group_name": S("CacheParameterGroupName"),
        "parameter_apply_status": S("ParameterApplyStatus"),
        "cache_node_ids_to_reboot": S("CacheNodeIdsToReboot", default=[]),
    }
    cache_parameter_group_name: Optional[str] = field(default=None)
    parameter_apply_status: Optional[str] = field(default=None)
    cache_node_ids_to_reboot: List[str] = field(factory=list)


@define(eq=False, slots=False)
class AwsElastiCacheCacheNode:
    kind: ClassVar[str] = "aws_elasti_cache_cache_node"
    mapping: ClassVar[Dict[str, Bender]] = {
        "cache_node_id": S("CacheNodeId"),
        "cache_node_status": S("CacheNodeStatus"),
        "cache_node_create_time": S("CacheNodeCreateTime"),
        "endpoint": S("Endpoint") >> Bend(AwsElastiCacheEndpoint.mapping),
        "parameter_group_status": S("ParameterGroupStatus"),
        "source_cache_node_id": S("SourceCacheNodeId"),
        "customer_availability_zone": S("CustomerAvailabilityZone"),
        "customer_outpost_arn": S("CustomerOutpostArn"),
    }
    cache_node_id: Optional[str] = field(default=None)
    cache_node_status: Optional[str] = field(default=None)
    cache_node_create_time: Optional[datetime] = field(default=None)
    endpoint: Optional[AwsElastiCacheEndpoint] = field(default=None)
    parameter_group_status: Optional[str] = field(default=None)
    source_cache_node_id: Optional[str] = field(default=None)
    customer_availability_zone: Optional[str] = field(default=None)
    customer_outpost_arn: Optional[str] = field(default=None)


@define(eq=False, slots=False)
class AwsElastiCacheSecurityGroupMembership:
    kind: ClassVar[str] = "aws_elasti_cache_security_group_membership"
    mapping: ClassVar[Dict[str, Bender]] = {"security_group_id": S("SecurityGroupId"), "status": S("Status")}
    security_group_id: Optional[str] = field(default=None)
    status: Optional[str] = field(default=None)


@define(eq=False, slots=False)
class AwsElastiCacheLogDeliveryConfiguration:
    kind: ClassVar[str] = "aws_elasti_cache_log_delivery_configuration"
    mapping: ClassVar[Dict[str, Bender]] = {
        "log_type": S("LogType"),
        "destination_type": S("DestinationType"),
        "destination_details": S("DestinationDetails") >> Bend(AwsElastiCacheDestinationDetails.mapping),
        "log_format": S("LogFormat"),
        "status": S("Status"),
        "message": S("Message"),
    }
    log_type: Optional[str] = field(default=None)
    destination_type: Optional[str] = field(default=None)
    destination_details: Optional[AwsElastiCacheDestinationDetails] = field(default=None)
    log_format: Optional[str] = field(default=None)
    status: Optional[str] = field(default=None)
    message: Optional[str] = field(default=None)


@define(eq=False, slots=False)
class AwsElastiCacheCacheCluster(ElastiCacheTaggable, AwsResource):
    kind: ClassVar[str] = "aws_elasti_cache_cache_cluster"
    api_spec: ClassVar[AwsApiSpec] = AwsApiSpec("elasticache", "describe-cache-clusters", "CacheClusters")
    mapping: ClassVar[Dict[str, Bender]] = {
        "id": S("CacheClusterId"),
        "tags": S("Tags", default=[]) >> ToDict(),
        "name": S("CacheClusterId"),
        "arn": S("ARN"),
        "ctime": S("CacheClusterCreateTime"),
        "mtime": K(None),
        "atime": K(None),
        "cluster_cache_cluster_id": S("CacheClusterId"),
        "cluster_configuration_endpoint": S("ConfigurationEndpoint") >> Bend(AwsElastiCacheEndpoint.mapping),
        "cluster_client_download_landing_page": S("ClientDownloadLandingPage"),
        "cluster_cache_node_type": S("CacheNodeType"),
        "cluster_engine": S("Engine"),
        "cluster_engine_version": S("EngineVersion"),
        "cluster_cache_cluster_status": S("CacheClusterStatus"),
        "cluster_num_cache_nodes": S("NumCacheNodes"),
        "cluster_preferred_availability_zone": S("PreferredAvailabilityZone"),
        "cluster_preferred_outpost_arn": S("PreferredOutpostArn"),
        "cluster_cache_cluster_create_time": S("CacheClusterCreateTime"),
        "cluster_preferred_maintenance_window": S("PreferredMaintenanceWindow"),
        "cluster_pending_modified_values": S("PendingModifiedValues")
        >> Bend(AwsElastiCachePendingModifiedValues.mapping),
        "cluster_notification_configuration": S("NotificationConfiguration")
        >> Bend(AwsElastiCacheNotificationConfiguration.mapping),
        "cluster_cache_security_groups": S("CacheSecurityGroups", default=[])
        >> ForallBend(AwsElastiCacheCacheSecurityGroupMembership.mapping),
        "cluster_cache_parameter_group": S("CacheParameterGroup")
        >> Bend(AwsElastiCacheCacheParameterGroupStatus.mapping),
        "cluster_cache_subnet_group_name": S("CacheSubnetGroupName"),
        "cluster_cache_nodes": S("CacheNodes", default=[]) >> ForallBend(AwsElastiCacheCacheNode.mapping),
        "cluster_auto_minor_version_upgrade": S("AutoMinorVersionUpgrade"),
        "cluster_security_groups": S("SecurityGroups", default=[])
        >> ForallBend(AwsElastiCacheSecurityGroupMembership.mapping),
        "cluster_replication_group_id": S("ReplicationGroupId"),
        "cluster_snapshot_retention_limit": S("SnapshotRetentionLimit"),
        "cluster_snapshot_window": S("SnapshotWindow"),
        "cluster_auth_token_enabled": S("AuthTokenEnabled"),
        "cluster_auth_token_last_modified_date": S("AuthTokenLastModifiedDate"),
        "cluster_transit_encryption_enabled": S("TransitEncryptionEnabled"),
        "cluster_at_rest_encryption_enabled": S("AtRestEncryptionEnabled"),
        "cluster_replication_group_log_delivery_enabled": S("ReplicationGroupLogDeliveryEnabled"),
        "cluster_log_delivery_configurations": S("LogDeliveryConfigurations", default=[])
        >> ForallBend(AwsElastiCacheLogDeliveryConfiguration.mapping),
    }
    cluster_cache_cluster_id: Optional[str] = field(default=None)
    cluster_configuration_endpoint: Optional[AwsElastiCacheEndpoint] = field(default=None)
    cluster_client_download_landing_page: Optional[str] = field(default=None)
    cluster_cache_node_type: Optional[str] = field(default=None)
    cluster_engine: Optional[str] = field(default=None)
    cluster_engine_version: Optional[str] = field(default=None)
    cluster_cache_cluster_status: Optional[str] = field(default=None)
    cluster_num_cache_nodes: Optional[int] = field(default=None)
    cluster_preferred_availability_zone: Optional[str] = field(default=None)
    cluster_preferred_outpost_arn: Optional[str] = field(default=None)
    cluster_preferred_maintenance_window: Optional[str] = field(default=None)
    cluster_pending_modified_values: Optional[AwsElastiCachePendingModifiedValues] = field(default=None)
    cluster_notification_configuration: Optional[AwsElastiCacheNotificationConfiguration] = field(default=None)
    cluster_cache_security_groups: List[AwsElastiCacheCacheSecurityGroupMembership] = field(factory=list)
    cluster_cache_parameter_group: Optional[AwsElastiCacheCacheParameterGroupStatus] = field(default=None)
    cluster_cache_subnet_group_name: Optional[str] = field(default=None)
    cluster_cache_nodes: List[AwsElastiCacheCacheNode] = field(factory=list)
    cluster_auto_minor_version_upgrade: Optional[bool] = field(default=None)
    cluster_security_groups: List[AwsElastiCacheSecurityGroupMembership] = field(factory=list)
    cluster_replication_group_id: Optional[str] = field(default=None)
    cluster_snapshot_retention_limit: Optional[int] = field(default=None)
    cluster_snapshot_window: Optional[str] = field(default=None)
    cluster_auth_token_enabled: Optional[bool] = field(default=None)
    cluster_auth_token_last_modified_date: Optional[datetime] = field(default=None)
    cluster_transit_encryption_enabled: Optional[bool] = field(default=None)
    cluster_at_rest_encryption_enabled: Optional[bool] = field(default=None)
    cluster_arn: Optional[str] = field(default=None)
    cluster_replication_group_log_delivery_enabled: Optional[bool] = field(default=None)
    cluster_log_delivery_configurations: List[AwsElastiCacheLogDeliveryConfiguration] = field(factory=list)


@define(eq=False, slots=False)
class AwsElastiCacheNodeGroupConfiguration:
    kind: ClassVar[str] = "aws_elasti_cache_node_group_configuration"
    mapping: ClassVar[Dict[str, Bender]] = {
        "node_group_id": S("NodeGroupId"),
        "slots": S("Slots"),
        "replica_count": S("ReplicaCount"),
        "primary_availability_zone": S("PrimaryAvailabilityZone"),
        "replica_availability_zones": S("ReplicaAvailabilityZones", default=[]),
        "primary_outpost_arn": S("PrimaryOutpostArn"),
        "replica_outpost_arns": S("ReplicaOutpostArns", default=[]),
    }
    node_group_id: Optional[str] = field(default=None)
    slots: Optional[str] = field(default=None)
    replica_count: Optional[int] = field(default=None)
    primary_availability_zone: Optional[str] = field(default=None)
    replica_availability_zones: List[str] = field(factory=list)
    primary_outpost_arn: Optional[str] = field(default=None)
    replica_outpost_arns: List[str] = field(factory=list)


@define(eq=False, slots=False)
class AwsElastiCacheNodeSnapshot:
    kind: ClassVar[str] = "aws_elasti_cache_node_snapshot"
    mapping: ClassVar[Dict[str, Bender]] = {
        "cache_cluster_id": S("CacheClusterId"),
        "node_group_id": S("NodeGroupId"),
        "cache_node_id": S("CacheNodeId"),
        "node_group_configuration": S("NodeGroupConfiguration") >> Bend(AwsElastiCacheNodeGroupConfiguration.mapping),
        "cache_size": S("CacheSize"),
        "cache_node_create_time": S("CacheNodeCreateTime"),
        "snapshot_create_time": S("SnapshotCreateTime"),
    }
    cache_cluster_id: Optional[str] = field(default=None)
    node_group_id: Optional[str] = field(default=None)
    cache_node_id: Optional[str] = field(default=None)
    node_group_configuration: Optional[AwsElastiCacheNodeGroupConfiguration] = field(default=None)
    cache_size: Optional[str] = field(default=None)
    cache_node_create_time: Optional[datetime] = field(default=None)
    snapshot_create_time: Optional[datetime] = field(default=None)


@define(eq=False, slots=False)
class AwsElastiCacheSnapshot(ElastiCacheTaggable, AwsResource, BaseSnapshot):
    kind: ClassVar[str] = "aws_elasti_cache_snapshot"
    api_spec: ClassVar[AwsApiSpec] = AwsApiSpec("elasticache", "describe-snapshots", "Snapshots")
    mapping: ClassVar[Dict[str, Bender]] = {
        "id": S("id"),
        "tags": S("Tags", default=[]) >> ToDict(),
        "name": S("SnapshotName"),
        "ctime": K(None),
        "mtime": K(None),
        "atime": K(None),
        "snapshot_snapshot_name": S("SnapshotName"),
        "snapshot_replication_group_id": S("ReplicationGroupId"),
        "snapshot_replication_group_description": S("ReplicationGroupDescription"),
        "snapshot_cache_cluster_id": S("CacheClusterId"),
        "snapshot_snapshot_status": S("SnapshotStatus"),
        "snapshot_snapshot_source": S("SnapshotSource"),
        "snapshot_cache_node_type": S("CacheNodeType"),
        "snapshot_engine": S("Engine"),
        "snapshot_engine_version": S("EngineVersion"),
        "snapshot_num_cache_nodes": S("NumCacheNodes"),
        "snapshot_preferred_availability_zone": S("PreferredAvailabilityZone"),
        "snapshot_preferred_outpost_arn": S("PreferredOutpostArn"),
        "snapshot_cache_cluster_create_time": S("CacheClusterCreateTime"),
        "snapshot_preferred_maintenance_window": S("PreferredMaintenanceWindow"),
        "snapshot_topic_arn": S("TopicArn"),
        "snapshot_port": S("Port"),
        "snapshot_cache_parameter_group_name": S("CacheParameterGroupName"),
        "snapshot_cache_subnet_group_name": S("CacheSubnetGroupName"),
        "snapshot_vpc_id": S("VpcId"),
        "snapshot_auto_minor_version_upgrade": S("AutoMinorVersionUpgrade"),
        "snapshot_snapshot_retention_limit": S("SnapshotRetentionLimit"),
        "snapshot_snapshot_window": S("SnapshotWindow"),
        "snapshot_num_node_groups": S("NumNodeGroups"),
        "snapshot_automatic_failover": S("AutomaticFailover"),
        "snapshot_node_snapshots": S("NodeSnapshots", default=[]) >> ForallBend(AwsElastiCacheNodeSnapshot.mapping),
        "snapshot_kms_key_id": S("KmsKeyId"),
        "snapshot_arn": S("ARN"),
        "snapshot_data_tiering": S("DataTiering"),
    }
    snapshot_snapshot_name: Optional[str] = field(default=None)
    snapshot_replication_group_id: Optional[str] = field(default=None)
    snapshot_replication_group_description: Optional[str] = field(default=None)
    snapshot_cache_cluster_id: Optional[str] = field(default=None)
    snapshot_snapshot_status: Optional[str] = field(default=None)
    snapshot_snapshot_source: Optional[str] = field(default=None)
    snapshot_cache_node_type: Optional[str] = field(default=None)
    snapshot_engine: Optional[str] = field(default=None)
    snapshot_engine_version: Optional[str] = field(default=None)
    snapshot_num_cache_nodes: Optional[int] = field(default=None)
    snapshot_preferred_availability_zone: Optional[str] = field(default=None)
    snapshot_preferred_outpost_arn: Optional[str] = field(default=None)
    snapshot_cache_cluster_create_time: Optional[datetime] = field(default=None)
    snapshot_preferred_maintenance_window: Optional[str] = field(default=None)
    snapshot_topic_arn: Optional[str] = field(default=None)
    snapshot_port: Optional[int] = field(default=None)
    snapshot_cache_parameter_group_name: Optional[str] = field(default=None)
    snapshot_cache_subnet_group_name: Optional[str] = field(default=None)
    snapshot_vpc_id: Optional[str] = field(default=None)
    snapshot_auto_minor_version_upgrade: Optional[bool] = field(default=None)
    snapshot_snapshot_retention_limit: Optional[int] = field(default=None)
    snapshot_snapshot_window: Optional[str] = field(default=None)
    snapshot_num_node_groups: Optional[int] = field(default=None)
    snapshot_automatic_failover: Optional[str] = field(default=None)
    snapshot_node_snapshots: List[AwsElastiCacheNodeSnapshot] = field(factory=list)
    snapshot_kms_key_id: Optional[str] = field(default=None)
    snapshot_arn: Optional[str] = field(default=None)
    snapshot_data_tiering: Optional[str] = field(default=None)


@define(eq=False, slots=False)
class AwsElastiCacheGlobalReplicationGroupInfo:
    kind: ClassVar[str] = "aws_elasti_cache_global_replication_group_info"
    mapping: ClassVar[Dict[str, Bender]] = {
        "global_replication_group_id": S("GlobalReplicationGroupId"),
        "global_replication_group_member_role": S("GlobalReplicationGroupMemberRole"),
    }
    global_replication_group_id: Optional[str] = field(default=None)
    global_replication_group_member_role: Optional[str] = field(default=None)


@define(eq=False, slots=False)
class AwsElastiCacheReshardingStatus:
    kind: ClassVar[str] = "aws_elasti_cache_resharding_status"
    mapping: ClassVar[Dict[str, Bender]] = {"slot_migration": S("SlotMigration", "ProgressPercentage")}
    slot_migration: Optional[float] = field(default=None)


@define(eq=False, slots=False)
class AwsElastiCacheUserGroupsUpdateStatus:
    kind: ClassVar[str] = "aws_elasti_cache_user_groups_update_status"
    mapping: ClassVar[Dict[str, Bender]] = {
        "user_group_ids_to_add": S("UserGroupIdsToAdd", default=[]),
        "user_group_ids_to_remove": S("UserGroupIdsToRemove", default=[]),
    }
    user_group_ids_to_add: List[str] = field(factory=list)
    user_group_ids_to_remove: List[str] = field(factory=list)


@define(eq=False, slots=False)
class AwsElastiCacheReplicationGroupPendingModifiedValues:
    kind: ClassVar[str] = "aws_elasti_cache_replication_group_pending_modified_values"
    mapping: ClassVar[Dict[str, Bender]] = {
        "primary_cluster_id": S("PrimaryClusterId"),
        "automatic_failover_status": S("AutomaticFailoverStatus"),
        "resharding": S("Resharding") >> Bend(AwsElastiCacheReshardingStatus.mapping),
        "auth_token_status": S("AuthTokenStatus"),
        "user_groups": S("UserGroups") >> Bend(AwsElastiCacheUserGroupsUpdateStatus.mapping),
        "log_delivery_configurations": S("LogDeliveryConfigurations", default=[])
        >> ForallBend(AwsElastiCachePendingLogDeliveryConfiguration.mapping),
    }
    primary_cluster_id: Optional[str] = field(default=None)
    automatic_failover_status: Optional[str] = field(default=None)
    resharding: Optional[AwsElastiCacheReshardingStatus] = field(default=None)
    auth_token_status: Optional[str] = field(default=None)
    user_groups: Optional[AwsElastiCacheUserGroupsUpdateStatus] = field(default=None)
    log_delivery_configurations: List[AwsElastiCachePendingLogDeliveryConfiguration] = field(factory=list)


@define(eq=False, slots=False)
class AwsElastiCacheNodeGroupMember:
    kind: ClassVar[str] = "aws_elasti_cache_node_group_member"
    mapping: ClassVar[Dict[str, Bender]] = {
        "cache_cluster_id": S("CacheClusterId"),
        "cache_node_id": S("CacheNodeId"),
        "read_endpoint": S("ReadEndpoint") >> Bend(AwsElastiCacheEndpoint.mapping),
        "preferred_availability_zone": S("PreferredAvailabilityZone"),
        "preferred_outpost_arn": S("PreferredOutpostArn"),
        "current_role": S("CurrentRole"),
    }
    cache_cluster_id: Optional[str] = field(default=None)
    cache_node_id: Optional[str] = field(default=None)
    read_endpoint: Optional[AwsElastiCacheEndpoint] = field(default=None)
    preferred_availability_zone: Optional[str] = field(default=None)
    preferred_outpost_arn: Optional[str] = field(default=None)
    current_role: Optional[str] = field(default=None)


@define(eq=False, slots=False)
class AwsElastiCacheNodeGroup:
    kind: ClassVar[str] = "aws_elasti_cache_node_group"
    mapping: ClassVar[Dict[str, Bender]] = {
        "node_group_id": S("NodeGroupId"),
        "status": S("Status"),
        "primary_endpoint": S("PrimaryEndpoint") >> Bend(AwsElastiCacheEndpoint.mapping),
        "reader_endpoint": S("ReaderEndpoint") >> Bend(AwsElastiCacheEndpoint.mapping),
        "slots": S("Slots"),
        "node_group_members": S("NodeGroupMembers", default=[]) >> ForallBend(AwsElastiCacheNodeGroupMember.mapping),
    }
    node_group_id: Optional[str] = field(default=None)
    status: Optional[str] = field(default=None)
    primary_endpoint: Optional[AwsElastiCacheEndpoint] = field(default=None)
    reader_endpoint: Optional[AwsElastiCacheEndpoint] = field(default=None)
    slots: Optional[str] = field(default=None)
    node_group_members: List[AwsElastiCacheNodeGroupMember] = field(factory=list)


@define(eq=False, slots=False)
class AwsElastiCacheReplicationGroup(ElastiCacheTaggable, AwsResource):
    kind: ClassVar[str] = "aws_elasti_cache_replication_group"
    api_spec: ClassVar[AwsApiSpec] = AwsApiSpec("elasticache", "describe-replication-groups", "ReplicationGroups")
    mapping: ClassVar[Dict[str, Bender]] = {
        "id": S("ReplicationGroupId"),
        "name": S("ReplicationGroupId"),
        "arn": S("ARN"),
        "ctime": S("ReplicationGroupCreateTime"),
        "mtime": K(None),
        "atime": K(None),
        "replication_group_description": S("Description"),
        "replication_group_global_replication_group_info": S("GlobalReplicationGroupInfo")
        >> Bend(AwsElastiCacheGlobalReplicationGroupInfo.mapping),
        "replication_group_status": S("Status"),
        "replication_group_pending_modified_values": S("PendingModifiedValues")
        >> Bend(AwsElastiCacheReplicationGroupPendingModifiedValues.mapping),
        "replication_group_member_clusters": S("MemberClusters", default=[]),
        "replication_group_node_groups": S("NodeGroups", default=[]) >> ForallBend(AwsElastiCacheNodeGroup.mapping),
        "replication_group_snapshotting_cluster_id": S("SnapshottingClusterId"),
        "replication_group_automatic_failover": S("AutomaticFailover"),
        "replication_group_multi_az": S("MultiAZ"),
        "replication_group_configuration_endpoint": S("ConfigurationEndpoint") >> Bend(AwsElastiCacheEndpoint.mapping),
        "replication_group_snapshot_retention_limit": S("SnapshotRetentionLimit"),
        "replication_group_snapshot_window": S("SnapshotWindow"),
        "replication_group_cluster_enabled": S("ClusterEnabled"),
        "replication_group_cache_node_type": S("CacheNodeType"),
        "replication_group_auth_token_enabled": S("AuthTokenEnabled"),
        "replication_group_auth_token_last_modified_date": S("AuthTokenLastModifiedDate"),
        "replication_group_transit_encryption_enabled": S("TransitEncryptionEnabled"),
        "replication_group_at_rest_encryption_enabled": S("AtRestEncryptionEnabled"),
        "replication_group_member_clusters_outpost_arns": S("MemberClustersOutpostArns", default=[]),
        "replication_group_kms_key_id": S("KmsKeyId"),
        "replication_group_arn": S("ARN"),
        "replication_group_user_group_ids": S("UserGroupIds", default=[]),
        "replication_group_log_delivery_configurations": S("LogDeliveryConfigurations", default=[])
        >> ForallBend(AwsElastiCacheLogDeliveryConfiguration.mapping),
        "replication_group_data_tiering": S("DataTiering"),
    }
    replication_group_replication_group_id: Optional[str] = field(default=None)
    replication_group_description: Optional[str] = field(default=None)
    replication_group_global_replication_group_info: Optional[AwsElastiCacheGlobalReplicationGroupInfo] = field(
        default=None
    )
    replication_group_status: Optional[str] = field(default=None)
    replication_group_pending_modified_values: Optional[AwsElastiCacheReplicationGroupPendingModifiedValues] = field(
        default=None
    )
    replication_group_member_clusters: List[str] = field(factory=list)
    replication_group_node_groups: List[AwsElastiCacheNodeGroup] = field(factory=list)
    replication_group_snapshotting_cluster_id: Optional[str] = field(default=None)
    replication_group_automatic_failover: Optional[str] = field(default=None)
    replication_group_multi_az: Optional[str] = field(default=None)
    replication_group_configuration_endpoint: Optional[AwsElastiCacheEndpoint] = field(default=None)
    replication_group_snapshot_retention_limit: Optional[int] = field(default=None)
    replication_group_snapshot_window: Optional[str] = field(default=None)
    replication_group_cluster_enabled: Optional[bool] = field(default=None)
    replication_group_cache_node_type: Optional[str] = field(default=None)
    replication_group_auth_token_enabled: Optional[bool] = field(default=None)
    replication_group_auth_token_last_modified_date: Optional[datetime] = field(default=None)
    replication_group_transit_encryption_enabled: Optional[bool] = field(default=None)
    replication_group_at_rest_encryption_enabled: Optional[bool] = field(default=None)
    replication_group_member_clusters_outpost_arns: List[str] = field(factory=list)
    replication_group_kms_key_id: Optional[str] = field(default=None)
    replication_group_arn: Optional[str] = field(default=None)
    replication_group_user_group_ids: List[str] = field(factory=list)
    replication_group_log_delivery_configurations: List[AwsElastiCacheLogDeliveryConfiguration] = field(factory=list)
    replication_group_data_tiering: Optional[str] = field(default=None)

    def delete_resource(self, client: AwsClient) -> bool:
        client.call(
            service=self.api_spec.service,
            action="delete_replication_group",
            result_name=None,
            ReplicationGroupId=self.id,
            RetainPrimaryCluster=False,
        )
        return True
