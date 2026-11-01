# AWS Architect Simulator — Design Decisions

## DD-001: Two Distinct Modes
**Decision:** Keep Architect Simulator and Client Proposal Studio as separate user experiences.

**Rationale:** Training and professional consulting have different workflows.

## DD-002: One Shared Architecture Engine
**Decision:** Both modes use one shared architecture data model and validation foundation.

**Rationale:** Avoid duplicate architecture logic and support reuse.

## DD-003: Local-First, No-Cost Development
**Decision:** Prefer local development and free/open-source tools. Do not introduce paid services without explicit approval.

**Rationale:** Keep the project affordable and under the user's control.

## DD-004: Preserve SQLite Initially
**Decision:** Keep the existing SQLite database during the current development phase.

**Rationale:** Preserve scenarios and progress; migrate only if needed.

## DD-005: Structured Architecture Data Is the Source of Truth
**Decision:** Store components, placements, configurations, and connections as structured data. Generate diagrams and exports from that model.

**Rationale:** Support validation and multiple views. Visio/Lucidchart compatibility must be tested, not assumed.

## DD-006: Continuous Documentation
**Decision:** Maintain project vision, requirements, design decisions, and development history throughout implementation.

**Rationale:** Documentation is part of the engineering deliverable and portfolio.

## DD-007: Separate Training Scores from Validation
**Decision:** Training scores belong only to Architect Simulator. Shared validation evaluates architecture properties independently.

**Rationale:** A learning score is not a production-readiness certification and must not appear in client proposals.
