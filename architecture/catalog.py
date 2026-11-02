
"""
AWS service catalog integration.

This module connects architecture resources to the existing
AWS service registry without creating a duplicate catalog.
"""


def get_service(service_id, service_records):
    """
    Find an AWS service by its stable service ID.

    Accepts either a dictionary of service records or
    an iterable of service dictionaries.
    """

    if isinstance(service_records, dict):
        if service_id in service_records:
            return service_records[service_id]

        records = service_records.values()
    else:
        records = service_records

    for service in records:
        if service.get("id") == service_id:
            return service

    return None


def service_exists(service_id, service_records):
    """Return True if the service exists in the registry."""

    return get_service(service_id, service_records) is not None


def create_resource(service_id, service_records, **kwargs):
    """
    Create an architecture resource using an existing
    AWS service definition.
    """

    from architecture.models import ArchitectureResource

    service = get_service(service_id, service_records)

    if service is None:
        raise ValueError(
            f"AWS service '{service_id}' was not found in the catalog."
        )

    return ArchitectureResource(
        service_id=service_id,
        name=service["name"],
        **kwargs
    )
