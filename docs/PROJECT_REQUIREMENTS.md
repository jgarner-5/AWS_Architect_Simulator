# AWS Architect Simulator — Project Requirements

## Current Foundation
- Flask, SQLAlchemy, and SQLite.
- Preserve existing scenarios, discovery flow, service selection, scoring, and diagrams.
- Preserve `simulator.db`; back it up before database/schema changes.
- Keep development local and free of paid dependencies.

## Architect Simulator
- Realistic customer scenarios and requirements.
- Discovery questions and service selection.
- Architecture views and design explanations.
- Training scores, hints, and debrief feedback.
- Distinguish training scores from production readiness.

## Client Proposal Studio
- Start from blank or from a template.
- Capture client requirements, assumptions, constraints, and risks.
- Add, configure, place, connect, and remove architecture components.
- Validate independently of training scores.
- Support cost-estimation workflows and proposal generation.
- Create editable diagrams where feasible; test export formats before claiming compatibility.

## Shared Architecture Model
Represent components with stable IDs and AWS service types, configuration properties, Region/AZ and VPC/subnet placement, connections/data flows, and validation findings. The diagram renderer displays this model; it is not the source of truth.

## Documentation and Portfolio
Maintain vision, requirements, decisions, and development history in `docs/`. Use Git for source history. Before public GitHub publication, exclude secrets, credentials, environment files, local databases, and confidential client information. Review every file before publishing.
