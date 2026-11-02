
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class ArchitectureResource:
    """
    Represents one AWS resource or service in an architecture.
    """

    service_id: str
    name: str
    resource_id: str = field(
        default_factory=lambda: str(uuid4())
    )
    configuration: dict[str, Any] = field(
        default_factory=dict
    )
    region: str | None = None
    availability_zone: str | None = None
    vpc_id: str | None = None
    subnet_id: str | None = None
    notes: str = ""


@dataclass
class ArchitectureConnection:
    """
    Represents a connection or data flow between resources.
    """

    source_id: str
    target_id: str
    connection_type: str = "network"
    description: str = ""
    connection_id: str = field(
        default_factory=lambda: str(uuid4())
    )


@dataclass
class Architecture:
    """
    Represents a complete cloud architecture design.
    """

    name: str
    architecture_id: str = field(
        default_factory=lambda: str(uuid4())
    )
    description: str = ""
    cloud_provider: str = "AWS"
    region: str = "us-east-1"
    resources: list[ArchitectureResource] = field(
        default_factory=list
    )
    connections: list[ArchitectureConnection] = field(
        default_factory=list
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def add_resource(self, resource: ArchitectureResource):
        self.resources.append(resource)

    def remove_resource(self, resource_id: str):
        self.resources = [
            resource
            for resource in self.resources
            if resource.resource_id != resource_id
        ]

        self.connections = [
            connection
            for connection in self.connections
            if connection.source_id != resource_id
            and connection.target_id != resource_id
        ]

    def add_connection(self, connection: ArchitectureConnection):
        self.connections.append(connection)
