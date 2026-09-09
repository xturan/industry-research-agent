# Group2 Design Example: Team Task Board

Status: approved_example

## Universal Mapping

| Universal role | Project-bound worker | Responsibility |
|---|---|---|
| `architecture-builder` | `task-workflow-architect` | Defines task status transition, audit boundary, and data ownership. |
| `feature-implementer` | `task-board-implementer` | Implements task creation, status updates, filters, and focused tests. |

## Round 1: Project Discovery

Project type:

- Generic SaaS task management feature.

Architecture assumptions:

- Backend API exists.
- Persistence layer exists.
- UI is out of scope for this example unless explicitly added.

Human confirmation:

- Status workflow is simple: `todo -> in_progress -> done`.

## Round 2: Role Proposal

`task-workflow-architect`:

- Owns transition policy and audit boundary.
- Does not implement all endpoints.

`task-board-implementer`:

- Owns concrete feature implementation.
- Does not modify PLAN or status files.

## Round 3: Scope Boundaries

Allowed writes:

- task-board source files;
- task-board tests;
- task-board docs.

Forbidden writes:

- billing;
- authentication;
- deployment;
- PLAN/STATUS.

## Round 4: Validation Handoff

Group3 owns:

- lint and test checks;
- acceptance cases TC-001 to TC-004;
- negative control for forbidden status transition.

Group2 may suggest tests but cannot be the only validator.

## Round 5: Human Approval

Decision:

- Approved for example use.
