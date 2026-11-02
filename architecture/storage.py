
"""
Architecture persistence layer.

Stores architecture designs independently of simulator attempts.
Uses SQLite and JSON serialization.
"""

import json
import sqlite3

from dataclasses import asdict
from datetime import datetime, timezone

from architecture.models import (
    Architecture,
    ArchitectureResource,
    ArchitectureConnection,
)


def initialize_storage(db_path):
    """Create the architecture table if it does not exist."""

    with sqlite3.connect(db_path) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS architecture_designs (
                architecture_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                cloud_provider TEXT NOT NULL,
                region TEXT NOT NULL,
                design_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)


def save_architecture(architecture, db_path):
    """Save a new architecture or update an existing one."""

    initialize_storage(db_path)

    now = datetime.now(timezone.utc).isoformat()

    design_data = {
        "resources": [
            asdict(resource)
            for resource in architecture.resources
        ],
        "connections": [
            asdict(connection)
            for connection in architecture.connections
        ],
        "metadata": architecture.metadata,
    }

    with sqlite3.connect(db_path) as connection:

        existing = connection.execute(
            """
            SELECT created_at
            FROM architecture_designs
            WHERE architecture_id = ?
            """,
            (architecture.architecture_id,)
        ).fetchone()

        created_at = existing[0] if existing else now

        connection.execute(
            """
            INSERT INTO architecture_designs (
                architecture_id,
                name,
                description,
                cloud_provider,
                region,
                design_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(architecture_id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                cloud_provider = excluded.cloud_provider,
                region = excluded.region,
                design_json = excluded.design_json,
                updated_at = excluded.updated_at
            """,
            (
                architecture.architecture_id,
                architecture.name,
                architecture.description,
                architecture.cloud_provider,
                architecture.region,
                json.dumps(design_data),
                created_at,
                now,
            )
        )

    return architecture.architecture_id


def load_architecture(architecture_id, db_path):
    """Load and reconstruct an architecture by its ID."""

    initialize_storage(db_path)

    with sqlite3.connect(db_path) as connection:

        row = connection.execute(
            """
            SELECT
                architecture_id,
                name,
                description,
                cloud_provider,
                region,
                design_json
            FROM architecture_designs
            WHERE architecture_id = ?
            """,
            (architecture_id,)
        ).fetchone()

    if row is None:
        return None

    design_data = json.loads(row[5])

    architecture = Architecture(
        name=row[1],
        architecture_id=row[0],
        description=row[2],
        cloud_provider=row[3],
        region=row[4],
        metadata=design_data.get("metadata", {}),
    )

    architecture.resources = [
        ArchitectureResource(**resource)
        for resource in design_data.get("resources", [])
    ]

    architecture.connections = [
        ArchitectureConnection(**connection)
        for connection in design_data.get("connections", [])
    ]

    return architecture


def list_architectures(db_path):
    """Return a list of saved architecture summaries."""

    initialize_storage(db_path)

    with sqlite3.connect(db_path) as connection:

        rows = connection.execute(
            """
            SELECT
                architecture_id,
                name,
                description,
                cloud_provider,
                region,
                updated_at
            FROM architecture_designs
            ORDER BY updated_at DESC
            """
        ).fetchall()

    return [
        {
            "architecture_id": row[0],
            "name": row[1],
            "description": row[2],
            "cloud_provider": row[3],
            "region": row[4],
            "updated_at": row[5],
        }
        for row in rows
    ]
