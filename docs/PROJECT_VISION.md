# AWS Architect Simulator — Project Vision

Build a local-first AWS architecture platform with two modes sharing one architecture engine.

## Architect Simulator
Training through customer scenarios, discovery questions, AWS service selection, architecture exercises, scoring, hints, and debrief feedback.

## Client Proposal Studio
A professional consulting workspace to capture client requirements, create architectures from blank designs or templates, configure AWS services, validate designs, estimate costs, generate proposals, and create diagrams.

## Shared Architecture Engine
Both modes share an AWS service catalog with stable component IDs, configurations, Region/AZ and VPC/subnet placement, connections/data flows, and architecture validation. Training scores remain separate from validation; Proposal Studio must not display training scores.

## Principles
- Local-first; avoid paid tools and services.
- Preserve working functionality and the existing SQLite database.
- Build incrementally and test changes.
- Document design decisions and development history.
- Prepare for GitHub publication without exposing secrets, private data, or confidential client information.
- Treat Visio/Lucidchart export as a future capability requiring actual compatibility tests.
