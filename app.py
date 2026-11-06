
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import json
import os
import ipaddress
import re
from pathlib import Path
from datetime import datetime

from architecture.storage import delete_architecture

from architecture import (
    Architecture,
    ArchitectureConnection,
    AWSVPC,
    AWSSubnet,
    create_resource,
    save_architecture,
    load_architecture,
    list_architectures,
)


app = Flask(__name__)
app.secret_key = os.environ.get(
    "SIMULATOR_SECRET_KEY",
    "local-dev-key-change-me"
)

BASE_DIR = Path(__file__).resolve().parent
DB = BASE_DIR / "simulator.db"
REGISTRY_FILE = BASE_DIR / "data" / "aws_services.json"


# ============================================================
# AWS SERVICE REGISTRY
# ============================================================

def load_service_registry():
    """Load and validate the AWS service catalog from JSON."""

    if not REGISTRY_FILE.exists():
        raise FileNotFoundError(
            f"AWS service registry not found: {REGISTRY_FILE}"
        )

    with REGISTRY_FILE.open("r", encoding="utf-8") as file:
        registry = json.load(file)

    services = registry.get("services")

    if not isinstance(services, list) or not services:
        raise ValueError(
            "The AWS service registry must contain a non-empty "
            "'services' list."
        )

    required_fields = {
        "id", "name", "category", "description", "scoring_group"
    }

    service_ids = set()
    catalog = []

    for service in services:
        missing_fields = required_fields - service.keys()

        if missing_fields:
            raise ValueError(
                f"Service entry is missing fields: "
                f"{', '.join(sorted(missing_fields))}"
            )

        service_id = service["id"]

        if service_id in service_ids:
            raise ValueError(
                f"Duplicate AWS service ID in registry: {service_id}"
            )

        service_ids.add(service_id)

        catalog.append((
            service_id,
            service["name"],
            service["category"],
            service["description"]
        ))

    return catalog, services


SERVICES, SERVICE_RECORDS = load_service_registry()

CORE = {
    service["id"]
    for service in SERVICE_RECORDS
    if service["scoring_group"].lower() == "core"
}

BONUS = {
    service["id"]
    for service in SERVICE_RECORDS
    if service["scoring_group"].lower() == "bonus"
}

CONDITIONAL = {
    service["id"]
    for service in SERVICE_RECORDS
    if service["scoring_group"].lower() == "conditional"
}

VALID_SCORING_GROUPS = {"core", "bonus", "conditional"}

for service in SERVICE_RECORDS:
    group = service["scoring_group"].lower()

    if group not in VALID_SCORING_GROUPS:
        raise ValueError(
            f"Unknown scoring group '{group}' for service "
            f"'{service['id']}'."
        )


# ============================================================
# SCENARIO
# ============================================================

SCENARIO = {
    "title": "The Growing Medical Practice",
    "industry": "Healthcare",
    "difficulty": "Beginner",
    "brief": (
        "Five medical clinics run a scheduling application on an "
        "aging server at the main office. Remote access is unreliable, "
        "the application is slow during busy periods, and leadership "
        "is concerned about losing patient records."
    ),
    "goals": [
        "Improve application availability",
        "Protect patient records",
        "Support growth from 120 to 300 employees",
        "Keep initial cloud spend near $4,000/month"
    ],
    "deployment_profile": {
        "region_count": 1,
        "availability_zones": {
            "count": 2,
            "status": "recommended",
            "reason": "Improve availability and support recovery within the one-hour business objective."
        },
        "subnets": {
            "public": {
                "per_az": 1,
                "purpose": "Internet-facing application entry points."
            },
            "private": {
                "per_az": 1,
                "purpose": "Application servers and database resources."
            }
        },
        "database": {
            "service": "rds",
            "high_availability": "recommended",
            "deployment": "multi_az",
            "reason": "The one-hour recovery objective supports evaluating Multi-AZ deployment."
        },
        "service_placement": {
            "public": ["alb"],
            "private": ["ec2", "autoscaling", "rds"],
            "regional": [
                "s3", "cloudwatch", "cloudtrail", "kms",
                "config", "backup"
            ],
            "global": ["iam", "route53"],
            "edge": ["waf"]
        }
    },
    "facts": {
        "users": (
            "How many users and how much traffic do you expect?",
            "There are 120 employees today. We expect to grow to 300 "
            "within three years. Traffic is heavier during weekday mornings."
        ),
        "data": (
            "How much data do you store, and how sensitive is it?",
            "We have 4 TB of patient records and documents. Patient data "
            "requires strict access controls, encryption, auditing, and "
            "appropriate regulatory safeguards."
        ),
        "recovery": (
            "How much downtime and data loss can the business tolerate?",
            "Scheduling should be restored within one hour after a major "
            "failure. We can tolerate losing no more than 15 minutes of data."
        ),
        "application": (
            "What does the application run on, and can it be modified?",
            "It is a Windows application connected to SQL Server. The "
            "vendor supports migration to compatible cloud infrastructure "
            "but has not approved a full rewrite."
        ),
        "budget": (
            "What is the budget and preferred migration approach?",
            "The initial budget is $4,000 per month. Leadership prefers "
            "a phased migration with minimal disruption."
        ),
        "network": (
            "How do clinics connect, and how do remote employees authenticate?",
            "Each clinic has its own Internet connection. Remote access "
            "uses a VPN, but identity controls and network configurations "
            "are inconsistent."
        )
    }
}


# ============================================================
# ARCHITECTURAL FEEDBACK
# ============================================================

NOTES = {
    "ec2": (
        "A plausible migration path for the vendor-supported legacy "
        "Windows application. Validate instance sizing, licensing, "
        "availability, and operating-system support."
    ),
    "vpc": (
        "A foundational network boundary. Design subnets, routing, "
        "security groups, and connectivity for the five clinics."
    ),
    "rds": (
        "Potentially appropriate because the application uses SQL Server. "
        "Validate SQL Server edition, licensing, feature compatibility, "
        "vendor support, performance, and migration constraints. EC2 "
        "may be preferable if the application requires unsupported features."
    ),
    "backup": (
        "Configure and restore-test backups against the stated recovery "
        "objectives: one-hour recovery time and 15-minute recovery point."
    ),
    "iam": (
        "Apply least privilege and role-based access. Workforce sign-in "
        "may require additional identity design beyond AWS resource IAM."
    ),
    "cloudwatch": (
        "Monitoring helps detect performance, availability, and "
        "operational issues. Define useful metrics, logs, alarms, "
        "and notification procedures."
    ),
    "cloudtrail": (
        "Useful audit evidence for AWS account activity. Configure "
        "appropriate retention and protection. CloudTrail alone "
        "does not establish healthcare compliance."
    ),
    "kms": (
        "Strong security improvement. Define encryption-key ownership, "
        "access policies, rotation requirements, and integration with "
        "supported services."
    ),
    "config": (
        "Can help detect configuration drift and assess resource "
        "configurations. Define rules, monitoring, and remediation "
        "responsibilities."
    ),
    "s3": (
        "Appropriate for suitable documents, exports, and backup copies. "
        "It is not a direct replacement for a live SQL database. "
        "Consider access controls, encryption, versioning, and retention."
    ),
    "alb": (
        "Potentially useful if the application can support multiple "
        "targets and requires traffic distribution. Validate application "
        "compatibility and availability requirements before implementation."
    ),
    "autoscaling": (
        "Potentially useful for variable workloads, but requires an "
        "application architecture that can safely run multiple instances. "
        "Validate session handling, application state, and licensing."
    ),
    "waf": (
        "Potentially useful if the scheduling application is exposed "
        "through a supported web entry point. Evaluate exposure, "
        "threat model, and application requirements."
    ),
    "route53": (
        "Potentially useful for DNS management, health checks, and "
        "routing. Evaluate the existing DNS environment and whether "
        "centralized management provides a business benefit."
    )
}


# ============================================================
# DATABASE
# ============================================================

def conn():
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    return connection


def init():
    with conn() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY,
                score INTEGER,
                selected TEXT,
                asked TEXT,
                created TEXT
            )
        """)


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    init()

    with conn() as connection:
        attempts = connection.execute(
            "SELECT * FROM attempts ORDER BY id DESC LIMIT 6"
        ).fetchall()

    return render_template(
        "index.html",
        s=SCENARIO,
        attempts=attempts
    )


# ============================================================
# SCENARIO
# ============================================================

@app.route("/play")
def play():
    return render_template(
        "play.html",
        s=SCENARIO,
        services=SERVICES,
        service_records=SERVICE_RECORDS,
        asked=session.get("asked", []),
        selected=session.get("selected", [])
    )


# ============================================================
# CUSTOMER DISCOVERY
# ============================================================

@app.post("/ask")
def ask():
    data = request.get_json(silent=True) or {}
    question_id = data.get("id")

    fact = SCENARIO["facts"].get(question_id)

    if not fact:
        return jsonify(error="Question not found"), 400

    asked = session.get("asked", [])

    if question_id not in asked:
        asked.append(question_id)

    session["asked"] = asked

    return jsonify(
        question=fact[0],
        answer=fact[1],
        asked=asked
    )


# ============================================================
# SERVICE SELECTION
# ============================================================

@app.post("/select")
def select():
    data = request.get_json(silent=True) or {}

    valid_ids = {service[0] for service in SERVICES}

    ids = [
        service_id
        for service_id in data.get("services", [])
        if service_id in valid_ids
    ]

    session["selected"] = ids

    return jsonify(saved=True)


# ============================================================
# EVALUATION
# ============================================================

@app.post("/evaluate")
def evaluate():
    selected = set(session.get("selected", []))
    asked = session.get("asked", [])

    total_questions = len(SCENARIO["facts"])

    discovery = round(20 * len(asked) / total_questions)
    core_score = round(45 * len(selected & CORE) / len(CORE))
    bonus_score = round(20 * len(selected & BONUS) / len(BONUS))
    foundation = 15
    penalty = 0

    score = max(
        0,
        min(100, foundation + discovery + core_score + bonus_score)
    )

    result = {
        "score": score,
        "foundation": foundation,
        "discovery": discovery,
        "core": core_score,
        "bonus": bonus_score,
        "penalty": penalty,
        "asked": len(asked),
        "totalq": total_questions,
        "missing": sorted(CORE - selected),
        "bonuses": sorted(selected & BONUS),
        "conditional": sorted(selected & CONDITIONAL),
        "selected": sorted(selected)
    }

    with conn() as connection:
        connection.execute(
            """
            INSERT INTO attempts(score, selected, asked, created)
            VALUES (?, ?, ?, ?)
            """,
            (
                score,
                json.dumps(sorted(selected)),
                json.dumps(asked),
                datetime.now().isoformat(timespec="minutes")
            )
        )

    session.pop("selected", None)
    session.pop("asked", None)

    return render_template(
        "results.html",
        r=result,
        notes=NOTES,
        names={
            service[0]: service[1]
            for service in SERVICES
        }
    )


# ============================================================
# RESET
# ============================================================

@app.post("/reset")
def reset():
    session.pop("selected", None)
    session.pop("asked", None)
    return redirect(url_for("play"))


# ============================================================
# CLIENT PROPOSAL STUDIO
# ============================================================

@app.route("/proposal")
def proposal():
    return render_template("proposal.html")


# ============================================================
# CLIENT PROPOSAL STUDIO API
# ============================================================

@app.route("/api/architecture/services", methods=["GET"])
def api_architecture_services():
    """Return the existing AWS service catalog."""

    records = (
        SERVICE_RECORDS.values()
        if isinstance(SERVICE_RECORDS, dict)
        else SERVICE_RECORDS
    )

    return jsonify([
        {
            "id": service.get("id"),
            "name": service.get("name"),
            "category": service.get("category", ""),
            "description": service.get("description", ""),
        }
        for service in records
    ])


@app.route("/api/demo-scenario", methods=["POST"])
def api_create_demo_scenario():
    """Create a realistic, fully populated multi-AZ clinic architecture demo."""
    architecture = Architecture(
        name="Harborview Medical — Highly Available Patient Portal",
        description=(
            "Scenario: a regional medical group needs a secure patient portal, "
            "appointment scheduling, and access to clinical records. The service "
            "must remain available if one Availability Zone fails. Patient data "
            "must stay in private subnets, be encrypted, backed up, monitored, "
            "and protected at the edge. This is a learning design, not a production blueprint."
        ),
        region="us-east-1",
    )
    vpc = AWSVPC(name="Production VPC", cidr_block="10.20.0.0/16")
    vpc.subnets = [
        AWSSubnet(name="Public Web-A", cidr_block="10.20.1.0/24", subnet_type="public", availability_zone="us-east-1a"),
        AWSSubnet(name="Public Web-B", cidr_block="10.20.2.0/24", subnet_type="public", availability_zone="us-east-1b"),
        AWSSubnet(name="Private App-A", cidr_block="10.20.11.0/24", subnet_type="private", availability_zone="us-east-1a"),
        AWSSubnet(name="Private App-B", cidr_block="10.20.12.0/24", subnet_type="private", availability_zone="us-east-1b"),
        AWSSubnet(name="Private Data-A", cidr_block="10.20.21.0/24", subnet_type="private", availability_zone="us-east-1a"),
        AWSSubnet(name="Private Data-B", cidr_block="10.20.22.0/24", subnet_type="private", availability_zone="us-east-1b"),
    ]
    architecture.vpcs.append(vpc)
    service_names = ["route53", "waf", "alb", "ec2", "autoscaling", "rds", "s3", "iam", "kms", "cloudwatch", "cloudtrail", "backup"]
    resources = {}
    for index, service_id in enumerate(service_names):
        resource = create_resource(service_id, SERVICE_RECORDS)
        architecture.add_resource(resource)
        resources[service_id] = resource
        architecture.metadata.setdefault("canvas_positions", {})[resource.resource_id] = {
            "x": 55 + (index % 3) * 310,
            "y": 55 + (index // 3) * 190,
        }
    # Place network-facing components in public subnets; application and data tiers remain private.
    public_a, public_b, app_a, app_b, data_a, data_b = vpc.subnets
    placements = {
        "alb": public_a, "ec2": app_a, "autoscaling": app_b,
        "rds": data_a,
    }
    for service_id, subnet in placements.items():
        r = resources[service_id]
        r.region, r.vpc_id, r.subnet_id, r.availability_zone = architecture.region, vpc.vpc_id, subnet.subnet_id, subnet.availability_zone
    for service_id in ("waf", "iam", "kms", "cloudwatch", "cloudtrail", "backup", "route53", "s3"):
        resources[service_id].region = architecture.region
    flows = [
        ("route53", "waf", "DNS directs users to the protected application"),
        ("waf", "alb", "Inspect and filter inbound HTTPS requests"),
        ("alb", "ec2", "Distribute requests to application instances"),
        ("ec2", "rds", "Application queries the private patient database"),
        ("ec2", "s3", "Store permitted documents and static assets"),
        ("iam", "ec2", "Instance role grants least-privilege access"),
        ("kms", "rds", "Encrypt database storage and supported backups"),
        ("cloudwatch", "ec2", "Collect application and instance telemetry"),
        ("cloudtrail", "iam", "Record account and identity activity"),
        ("backup", "rds", "Protect database recovery points"),
    ]
    for source, target, description in flows:
        architecture.add_connection(ArchitectureConnection(
            source_id=resources[source].resource_id,
            target_id=resources[target].resource_id,
            description=description,
        ))
    architecture.metadata["scenario"] = {
        "type": "guided_demo",
        "client": "Harborview Medical Group",
        "objective": "Secure, multi-AZ patient portal with private clinical data",
        "acceptance_checks": [
            "Two public subnets span two Availability Zones",
            "Application and database tiers use private subnets",
            "Database is not directly exposed to the internet",
            "Inbound traffic passes through WAF and the load balancer",
            "Identity, encryption, monitoring, audit, and backup services are represented",
        ],
    }
    save_architecture(architecture, DB)
    return jsonify({"architecture_id": architecture.architecture_id, "name": architecture.name, "message": "Guided scenario created."}), 201


@app.route("/api/architectures", methods=["GET", "POST"])
def api_architectures():
    """List saved architectures or create a new one."""

    if request.method == "GET":
        return jsonify(list_architectures(DB))

    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()

    if not name:
        return jsonify(error="Architecture name is required."), 400

    architecture = Architecture(
        name=name,
        description=data.get("description", "").strip(),
        region=data.get("region", "us-east-1"),
    )

    save_architecture(architecture, DB)

    return jsonify({
        "architecture_id": architecture.architecture_id,
        "name": architecture.name,
        "message": "Architecture created successfully."
    }), 201


@app.route("/api/architectures/<architecture_id>", methods=["DELETE"])
def api_delete_architecture(architecture_id):
    """Delete only the requested saved architecture design."""

    if not delete_architecture(architecture_id, DB):
        return jsonify(error="Architecture not found. It may already have been deleted."), 404

    return jsonify({
        "architecture_id": architecture_id,
        "message": "Architecture deleted successfully.",
    }), 200


@app.route("/api/architectures/<architecture_id>", methods=["PUT"])
def api_update_architecture(architecture_id):
    """Update editable architecture-level settings without replacing its design."""
    architecture = load_architecture(architecture_id, DB)
    if architecture is None:
        return jsonify(error="Architecture not found."), 404

    data = request.get_json(silent=True) or {}
    name = data.get("name", architecture.name)
    description = data.get("description", architecture.description)
    cloud_provider = data.get("cloud_provider", architecture.cloud_provider)
    region = data.get("region", architecture.region)

    if not isinstance(name, str) or not name.strip():
        return jsonify(error="Architecture name is required."), 400
    if not isinstance(description, str) or not isinstance(cloud_provider, str) or not isinstance(region, str):
        return jsonify(error="Description, cloud provider, and region must be text values."), 400

    architecture.name = name.strip()
    architecture.description = description.strip()
    architecture.cloud_provider = cloud_provider.strip() or "AWS"
    new_region = region.strip() or architecture.region
    if not _valid_region(new_region):
        return jsonify(error="Enter a valid AWS Region identifier, such as us-east-1."), 400
    for vpc in architecture.vpcs:
        for subnet in vpc.subnets:
            if subnet.availability_zone and not _valid_az_for_region(subnet.availability_zone, new_region):
                return jsonify(error=(
                    f"Cannot change Region: subnet '{subnet.name}' uses "
                    f"Availability Zone {subnet.availability_zone}. Reassign or remove that subnet first."
                )), 400
    architecture.region = new_region
    save_architecture(architecture, DB)
    return jsonify({"architecture_id": architecture_id, "name": architecture.name,
                    "description": architecture.description, "cloud_provider": architecture.cloud_provider,
                    "region": architecture.region, "message": "Architecture settings updated."})


@app.route("/api/architectures/<architecture_id>/connections/<connection_id>", methods=["PATCH", "DELETE"])
def api_manage_architecture_connection(architecture_id, connection_id):
    """Edit a connection description/type or remove one connection."""
    architecture = load_architecture(architecture_id, DB)
    if architecture is None:
        return jsonify(error="Architecture not found."), 404

    match = next((item for item in architecture.connections if item.connection_id == connection_id), None)
    if match is None:
        return jsonify(error="Connection not found."), 404

    if request.method == "DELETE":
        architecture.connections = [item for item in architecture.connections if item.connection_id != connection_id]
        save_architecture(architecture, DB)
        return jsonify({"connection_id": connection_id, "message": "Connection deleted."})

    data = request.get_json(silent=True) or {}
    description = data.get("description", match.description)
    connection_type = data.get("connection_type", match.connection_type)
    if not isinstance(description, str) or not isinstance(connection_type, str):
        return jsonify(error="Connection description and type must be text values."), 400
    match.description = description.strip()
    match.connection_type = connection_type.strip() or "network"
    save_architecture(architecture, DB)
    return jsonify({"connection_id": connection_id, "description": match.description,
                    "connection_type": match.connection_type, "message": "Connection updated."})


@app.route("/api/architectures/<architecture_id>", methods=["GET"])
def api_get_architecture(architecture_id):
    """Retrieve a saved architecture, including canvas positions."""

    architecture = load_architecture(architecture_id, DB)

    if architecture is None:
        return jsonify(error="Architecture not found."), 404

    positions = architecture.metadata.get("canvas_positions", {})

    resources = []

    for index, resource in enumerate(architecture.resources):
        default_position = {
            "x": 100 + index * 40,
            "y": 100 + index * 40
        }

        resources.append({
            "resource_id": resource.resource_id,
            "service_id": resource.service_id,
            "name": resource.name,
            "configuration": resource.configuration,
            "region": resource.region,
            "availability_zone": resource.availability_zone,
            "vpc_id": resource.vpc_id,
            "subnet_id": resource.subnet_id,
            "subnet_ids": architecture.metadata.get("resource_subnet_ids", {}).get(
                resource.resource_id, ([resource.subnet_id] if resource.subnet_id else [])
            ),
            "notes": resource.notes,
            "position": positions.get(
                resource.resource_id,
                default_position
            )
        })

    return jsonify({
        "architecture_id": architecture.architecture_id,
        "name": architecture.name,
        "description": architecture.description,
        "cloud_provider": architecture.cloud_provider,
        "region": architecture.region,
        "resources": resources,
        "connections": [
            {
                "connection_id": item.connection_id,
                "source_id": item.source_id,
                "target_id": item.target_id,
                "connection_type": item.connection_type,
                "description": item.description,
            }
            for item in architecture.connections
        ],
        "metadata": architecture.metadata,
        "vpcs": [{"vpc_id": v.vpc_id, "name": v.name, "cidr_block": v.cidr_block,
                  "subnets": [{"subnet_id": n.subnet_id, "name": n.name,
                               "cidr_block": n.cidr_block, "subnet_type": n.subnet_type,
                               "availability_zone": n.availability_zone} for n in v.subnets]}
                 for v in architecture.vpcs],
    })


@app.route(
    "/api/architectures/<architecture_id>/resources",
    methods=["POST"]
)
def api_add_architecture_resource(architecture_id):
    """Add an AWS service to an architecture."""

    architecture = load_architecture(architecture_id, DB)

    if architecture is None:
        return jsonify(error="Architecture not found."), 404

    data = request.get_json(silent=True) or {}
    service_id = data.get("service_id", "").strip()

    if not service_id:
        return jsonify(error="Service ID is required."), 400

    try:
        resource = create_resource(service_id, SERVICE_RECORDS)
    except ValueError as error:
        return jsonify(error=str(error)), 400

    architecture.add_resource(resource)

    positions = architecture.metadata.setdefault(
        "canvas_positions", {}
    )

    index = len(architecture.resources) - 1

    positions[resource.resource_id] = {
        "x": 80 + (index % 3) * 320,
        "y": 80 + (index // 3) * 190
    }

    save_architecture(architecture, DB)

    return jsonify({
        "resource_id": resource.resource_id,
        "service_id": resource.service_id,
        "name": resource.name,
        "position": positions[resource.resource_id],
        "message": "Resource added successfully."
    }), 201



@app.route(
    "/api/architectures/<architecture_id>/resources/<resource_id>",
    methods=["DELETE"]
)
def api_delete_architecture_resource(architecture_id, resource_id):
    """Remove a resource, its connections, and its saved canvas position."""
    architecture = load_architecture(architecture_id, DB)
    if architecture is None:
        return jsonify(error="Architecture not found."), 404

    resource = next((r for r in architecture.resources if r.resource_id == resource_id), None)
    if resource is None:
        return jsonify(error="Resource not found."), 404

    architecture.resources = [r for r in architecture.resources if r.resource_id != resource_id]
    architecture.connections = [
        c for c in architecture.connections
        if c.source_id != resource_id and c.target_id != resource_id
    ]
    positions = architecture.metadata.get("canvas_positions", {})
    positions.pop(resource_id, None)
    mappings = architecture.metadata.get("resource_subnet_ids", {})
    mappings.pop(resource_id, None)

    save_architecture(architecture, DB)
    return jsonify({
        "resource_id": resource_id,
        "message": "Resource and its connections removed."
    })


@app.route(
    "/api/architectures/<architecture_id>/positions",
    methods=["POST"]
)
def api_save_architecture_positions(architecture_id):
    """Save the canvas positions of architecture resources."""

    architecture = load_architecture(architecture_id, DB)

    if architecture is None:
        return jsonify(error="Architecture not found."), 404

    data = request.get_json(silent=True) or {}
    submitted_positions = data.get("positions")

    if not isinstance(submitted_positions, dict):
        return jsonify(error="A positions object is required."), 400

    valid_ids = {
        resource.resource_id
        for resource in architecture.resources
    }

    positions = architecture.metadata.setdefault(
        "canvas_positions", {}
    )

    for resource_id, position in submitted_positions.items():
        if resource_id not in valid_ids:
            return jsonify(
                error=f"Unknown resource ID: {resource_id}"
            ), 400

        if not isinstance(position, dict):
            return jsonify(
                error=f"Invalid position for resource {resource_id}."
            ), 400

        x = position.get("x")
        y = position.get("y")

        # Reject non-numeric, boolean, infinite, and excessively
        # large coordinates.
        if (
            isinstance(x, bool) or isinstance(y, bool)
            or not isinstance(x, (int, float))
            or not isinstance(y, (int, float))
            or not (-10000 <= x <= 100000)
            or not (-10000 <= y <= 100000)
        ):
            return jsonify(
                error=f"Invalid coordinates for resource {resource_id}."
            ), 400

        positions[resource_id] = {
            "x": round(x),
            "y": round(y)
        }

    save_architecture(architecture, DB)

    return jsonify({
        "saved": True,
        "positions": positions,
        "message": "Architecture positions saved successfully."
    })


# ============================================================
# ARCHITECTURE CONNECTION API
# ============================================================

@app.route(
    "/api/architectures/<architecture_id>/connections",
    methods=["POST"]
)
def api_add_architecture_connection(architecture_id):
    """Connect two existing resources in an architecture."""

    architecture = load_architecture(architecture_id, DB)

    if architecture is None:
        return jsonify(error="Architecture not found."), 404

    data = request.get_json(silent=True) or {}
    source_id = data.get("source_id")
    target_id = data.get("target_id")

    if not isinstance(source_id, str) or not isinstance(target_id, str):
        return jsonify(
            error="Source and destination resource IDs are required."
        ), 400

    resource_ids = {
        resource.resource_id
        for resource in architecture.resources
    }

    if source_id not in resource_ids:
        return jsonify(
            error="Source resource does not exist in this architecture."
        ), 400

    if target_id not in resource_ids:
        return jsonify(
            error="Destination resource does not exist in this architecture."
        ), 400

    if source_id == target_id:
        return jsonify(error="A resource cannot connect to itself."), 400

    for existing in architecture.connections:
        if (
            existing.source_id == source_id
            and existing.target_id == target_id
        ):
            return jsonify(error="This connection already exists."), 409

    connection = ArchitectureConnection(
        source_id=source_id,
        target_id=target_id,
        connection_type=data.get("connection_type", "network"),
        description=data.get("description", "")
    )

    architecture.add_connection(connection)
    save_architecture(architecture, DB)

    return jsonify({
        "connection_id": connection.connection_id,
        "source_id": connection.source_id,
        "target_id": connection.target_id,
        "connection_type": connection.connection_type,
        "description": connection.description,
        "message": "Architecture connection created successfully."
    }), 201




# ============================================================
# INFRASTRUCTURE PLACEMENT API — PHASE 4
# ============================================================

def _parse_ipv4_network(value, label):
    """Parse a canonical IPv4 network or raise a useful ValueError."""
    try:
        network = ipaddress.ip_network(str(value).strip(), strict=False)
    except ValueError as exc:
        raise ValueError(f"Enter a valid {label} CIDR block.") from exc
    if not isinstance(network, ipaddress.IPv4Network):
        raise ValueError(f"{label} must be an IPv4 CIDR block.")
    return network


def _valid_region(value):
    """Validate the syntax of a standard AWS commercial Region identifier."""
    return bool(re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-[0-9]", str(value or "").strip()))


def _valid_az_for_region(availability_zone, region):
    """Validate standard AZ names such as us-east-1a against their Region."""
    return bool(re.fullmatch(re.escape(region) + r"[a-z]", str(availability_zone or "").strip()))


@app.route("/api/architectures/<architecture_id>/infrastructure", methods=["GET"])
def api_get_infrastructure(architecture_id):
    architecture = load_architecture(architecture_id, DB)
    if architecture is None:
        return jsonify(error="Architecture not found."), 404
    return jsonify({"region": architecture.region, "vpcs": [
        {"vpc_id": v.vpc_id, "name": v.name, "cidr_block": v.cidr_block,
         "subnets": [{"subnet_id": n.subnet_id, "name": n.name,
                      "cidr_block": n.cidr_block, "subnet_type": n.subnet_type,
                      "availability_zone": n.availability_zone} for n in v.subnets]}
        for v in architecture.vpcs
    ]})


@app.route("/api/architectures/<architecture_id>/infrastructure", methods=["POST"])
def api_update_infrastructure(architecture_id):
    architecture = load_architecture(architecture_id, DB)
    if architecture is None:
        return jsonify(error="Architecture not found."), 404

    data = request.get_json(silent=True) or {}
    action = data.get("action")

    if action == "region":
        region = str(data.get("region", "")).strip()
        if not _valid_region(region):
            return jsonify(error="Enter a valid AWS Region identifier, such as us-east-1."), 400
        # Do not silently strand existing subnets in a different Region.
        for vpc in architecture.vpcs:
            for subnet in vpc.subnets:
                if subnet.availability_zone and not _valid_az_for_region(subnet.availability_zone, region):
                    return jsonify(error=(
                        f"Cannot change Region: subnet '{subnet.name}' uses "
                        f"Availability Zone {subnet.availability_zone}. Reassign or remove that subnet first."
                    )), 400
        architecture.region = region

    elif action == "vpc":
        name = str(data.get("name", "")).strip()
        if not name:
            return jsonify(error="VPC name is required."), 400
        try:
            network = _parse_ipv4_network(data.get("cidr_block", ""), "VPC")
        except ValueError as error:
            return jsonify(error=str(error)), 400
        for existing in architecture.vpcs:
            existing_network = _parse_ipv4_network(existing.cidr_block, "existing VPC")
            if network.overlaps(existing_network):
                return jsonify(error=(
                    f"VPC CIDR {network} overlaps existing VPC "
                    f"'{existing.name}' ({existing_network})."
                )), 409
        architecture.vpcs.append(AWSVPC(name=name, cidr_block=str(network)))

    elif action == "subnet":
        vpc = next((v for v in architecture.vpcs if v.vpc_id == data.get("vpc_id")), None)
        if vpc is None:
            return jsonify(error="Select an existing VPC."), 400
        name = str(data.get("name", "")).strip()
        kind = data.get("subnet_type", "private")
        az = str(data.get("availability_zone", "")).strip()
        if not name or kind not in ("public", "private"):
            return jsonify(error="Provide a subnet name and public/private type."), 400
        if not _valid_az_for_region(az, architecture.region):
            return jsonify(error=(
                f"Availability Zone must belong to {architecture.region} "
                f"(for example, {architecture.region}a)."
            )), 400
        try:
            network = _parse_ipv4_network(data.get("cidr_block", ""), "subnet")
            parent = _parse_ipv4_network(vpc.cidr_block, "parent VPC")
        except ValueError as error:
            return jsonify(error=str(error)), 400
        if not network.subnet_of(parent):
            return jsonify(error="Subnet CIDR must be contained within its VPC CIDR."), 400
        for existing in vpc.subnets:
            existing_network = _parse_ipv4_network(existing.cidr_block, "existing subnet")
            if network.overlaps(existing_network):
                return jsonify(error=(
                    f"Subnet CIDR {network} overlaps existing subnet "
                    f"'{existing.name}' ({existing_network})."
                )), 409
        vpc.subnets.append(AWSSubnet(
            name=name, cidr_block=str(network), subnet_type=kind,
            availability_zone=az
        ))

    elif action == "placement":
        resource = next((r for r in architecture.resources if r.resource_id == data.get("resource_id")), None)
        if resource is None:
            return jsonify(error="Resource not found."), 404
        vpc_id = data.get("vpc_id")
        subnet_ids = data.get("subnet_ids")
        if subnet_ids is None:
            single_subnet_id = data.get("subnet_id")
            subnet_ids = [single_subnet_id] if single_subnet_id else []
        if not isinstance(subnet_ids, list):
            return jsonify(error="Subnet selection must be a list."), 400
        vpc = next((v for v in architecture.vpcs if v.vpc_id == vpc_id), None) if vpc_id else None
        if vpc_id and vpc is None:
            return jsonify(error="VPC not found."), 400
        selected_subnets = []
        for selected_id in subnet_ids:
            subnet = next((n for n in vpc.subnets if n.subnet_id == selected_id), None) if vpc else None
            if subnet is None:
                return jsonify(error="One or more selected subnets were not found in the selected VPC."), 400
            selected_subnets.append(subnet)
        # Preserve legacy single-subnet fields for existing renderer/clients.
        resource.region = architecture.region
        resource.vpc_id = vpc.vpc_id if vpc else None
        resource.subnet_id = selected_subnets[0].subnet_id if selected_subnets else None
        resource.availability_zone = selected_subnets[0].availability_zone if selected_subnets else None
        mappings = architecture.metadata.setdefault("resource_subnet_ids", {})
        if selected_subnets:
            mappings[resource.resource_id] = [n.subnet_id for n in selected_subnets]
        else:
            mappings.pop(resource.resource_id, None)

    else:
        return jsonify(error="Unknown infrastructure action."), 400

    save_architecture(architecture, DB)
    return jsonify({"saved": True, "message": "Infrastructure updated successfully."}), 200


# ============================================================
# APPLICATION START
# ============================================================

if __name__ == "__main__":
    init()
    app.run(debug=True, port=5000)
