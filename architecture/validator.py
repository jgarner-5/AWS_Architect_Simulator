
"""
Architecture validation engine.

Initial checks focus on data integrity and relationships.
AWS-specific deployment rules will be added in later phases.
"""

from dataclasses import dataclass, field


@dataclass
class ValidationIssue:
    severity: str
    code: str
    message: str
    resource_id: str | None = None


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self):
        return [
            issue for issue in self.issues
            if issue.severity == "error"
        ]

    @property
    def warnings(self):
        return [
            issue for issue in self.issues
            if issue.severity == "warning"
        ]

    @property
    def is_valid(self):
        return len(self.errors) == 0

    def add_error(self, code, message, resource_id=None):
        self.issues.append(
            ValidationIssue(
                severity="error",
                code=code,
                message=message,
                resource_id=resource_id
            )
        )

    def add_warning(self, code, message, resource_id=None):
        self.issues.append(
            ValidationIssue(
                severity="warning",
                code=code,
                message=message,
                resource_id=resource_id
            )
        )


def validate_architecture(architecture):
    """
    Validate architecture structure and connection integrity.

    Returns a ValidationResult containing errors and warnings.
    """

    result = ValidationResult()

    if not architecture.name.strip():
        result.add_error(
            "MISSING_ARCHITECTURE_NAME",
            "The architecture must have a name."
        )

    resource_ids = set()

    for resource in architecture.resources:

        if not resource.service_id:
            result.add_error(
                "MISSING_SERVICE_ID",
                "An architecture resource has no service ID.",
                resource.resource_id
            )

        if not resource.name.strip():
            result.add_error(
                "MISSING_RESOURCE_NAME",
                "An architecture resource has no name.",
                resource.resource_id
            )

        if resource.resource_id in resource_ids:
            result.add_error(
                "DUPLICATE_RESOURCE_ID",
                "Multiple resources share the same resource ID.",
                resource.resource_id
            )

        resource_ids.add(resource.resource_id)

    connection_ids = set()

    for connection in architecture.connections:

        if connection.connection_id in connection_ids:
            result.add_error(
                "DUPLICATE_CONNECTION_ID",
                "Multiple connections share the same connection ID."
            )

        connection_ids.add(connection.connection_id)

        if connection.source_id not in resource_ids:
            result.add_error(
                "INVALID_CONNECTION_SOURCE",
                "A connection references a source resource that does not exist."
            )

        if connection.target_id not in resource_ids:
            result.add_error(
                "INVALID_CONNECTION_TARGET",
                "A connection references a target resource that does not exist."
            )

        if connection.source_id == connection.target_id:
            result.add_error(
                "SELF_CONNECTION",
                "A resource cannot connect to itself."
            )

    if not architecture.resources:
        result.add_warning(
            "EMPTY_ARCHITECTURE",
            "The architecture does not contain any resources yet."
        )

    return result
