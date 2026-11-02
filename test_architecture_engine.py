
import os
import tempfile

from architecture import (
    Architecture,
    ArchitectureResource,
    ArchitectureConnection,
    validate_architecture,
    create_resource,
    service_exists,
    save_architecture,
    load_architecture,
    list_architectures,
)

from app import SERVICE_RECORDS


# ============================================================
# CREATE TEST ARCHITECTURE
# ============================================================

design = Architecture(
    name="Medical Practice Cloud Architecture",
    description="Initial architecture model test"
)


# Create two resources
load_balancer = ArchitectureResource(
    service_id="alb",
    name="Application Load Balancer"
)

application = ArchitectureResource(
    service_id="ec2",
    name="EC2 Application Server"
)


# Add resources
design.add_resource(load_balancer)
design.add_resource(application)


# Connect the resources
design.add_connection(
    ArchitectureConnection(
        source_id=load_balancer.resource_id,
        target_id=application.resource_id,
        description="Application traffic"
    )
)


# ============================================================
# TEST 1 — ARCHITECTURE ENGINE
# ============================================================

result = validate_architecture(design)

print("\nARCHITECTURE ENGINE TEST")
print("------------------------")
print("Architecture:", design.name)
print("Resources:", len(design.resources))
print("Connections:", len(design.connections))
print("Valid:", result.is_valid)
print("Errors:", len(result.errors))
print("Warnings:", len(result.warnings))

for issue in result.issues:
    print(issue.severity.upper(), issue.code, issue.message)


# ============================================================
# TEST 2 — AWS SERVICE CATALOG INTEGRATION
# ============================================================

print("\nAWS SERVICE CATALOG INTEGRATION")
print("-------------------------------")

print("ALB exists:", service_exists("alb", SERVICE_RECORDS))
print("EC2 exists:", service_exists("ec2", SERVICE_RECORDS))

catalog_resource = create_resource(
    "alb",
    SERVICE_RECORDS
)

print("Created resource:", catalog_resource.name)
print("Service ID:", catalog_resource.service_id)


# ============================================================
# TEST 3 — INVALID SERVICE HANDLING
# ============================================================

print("\nINVALID SERVICE TEST")
print("--------------------")

try:
    create_resource(
        "not-a-real-aws-service",
        SERVICE_RECORDS
    )

    print("ERROR: Invalid service was accepted.")

except ValueError as error:
    print("Invalid service correctly rejected.")
    print("Message:", error)


# ============================================================
# TEST 4 — ARCHITECTURE STORAGE
# ============================================================

print("\nARCHITECTURE STORAGE TEST")
print("-------------------------")

with tempfile.TemporaryDirectory() as temp_dir:

    test_db = os.path.join(
        temp_dir,
        "architecture_test.db"
    )

    # Save the architecture
    saved_id = save_architecture(
        design,
        test_db
    )

    print("Saved architecture ID:", saved_id)

    # Load the architecture
    loaded_design = load_architecture(
        saved_id,
        test_db
    )

    print("Loaded architecture:", loaded_design.name)
    print("Loaded resources:", len(loaded_design.resources))
    print("Loaded connections:", len(loaded_design.connections))

    # Validate the loaded architecture
    loaded_result = validate_architecture(loaded_design)

    print("Loaded architecture valid:", loaded_result.is_valid)

    # List saved architectures
    saved_designs = list_architectures(test_db)

    print("Saved designs:", len(saved_designs))

    # Test nonexistent architecture ID
    missing_design = load_architecture(
        "does-not-exist",
        test_db
    )

    print("Missing design returns None:", missing_design is None)


# ============================================================
# END OF ARCHITECTURE ENGINE TESTS
# ============================================================

print("\nALL ARCHITECTURE ENGINE TESTS COMPLETED")
print("---------------------------------------")
