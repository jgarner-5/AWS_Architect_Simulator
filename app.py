
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime


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
        "id",
        "name",
        "category",
        "description",
        "scoring_group"
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

        # Preserve the tuple format expected by play.html.
        catalog.append((
            service_id,
            service["name"],
            service["category"],
            service["description"]
        ))

    return catalog, services


SERVICES, SERVICE_RECORDS = load_service_registry()


# Derive scoring groups from the registry.
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

# Ensure every registered service has a recognized scoring group.
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
                "s3",
                "cloudwatch",
                "cloudtrail",
                "kms",
                "config",
                "backup"
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

    # Discovery: 20 points
    discovery = round(
        20 * len(asked) / total_questions
    )

    # Core architecture: 45 points
    core_score = round(
        45 * len(selected & CORE) / len(CORE)
    )

    # Additional improvements: 20 points
    bonus_score = round(
        20 * len(selected & BONUS) / len(BONUS)
    )

    # Architecture foundation: 15 points
    foundation = 15

    # Conditional services do not receive automatic penalties.
    # They receive architectural feedback instead.
    penalty = 0

    score = max(
        0,
        min(
            100,
            foundation + discovery + core_score + bonus_score
        )
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

    # Preserve the existing attempt history.
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

    # Clear the current attempt after evaluation.
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
# APPLICATION START
# ============================================================

if __name__ == "__main__":
    init()
    app.run(debug=True, port=5000)
