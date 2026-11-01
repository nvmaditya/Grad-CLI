# Design history

These are the design notes GradBot was built from. They record decisions
and alternatives; they are not user documentation and may describe things
that were never built. The README roadmap says what is planned.

| Document | Status |
|---|---|
| [course-repo-spec.md](course-repo-spec.md) | Spec for running a course from a private `gradecli` repo on a free GitHub organization. Sessions 1–2 (classroom files, grade workflow text) are built; 3–8 are planned. |
| [course-repo-plan.md](course-repo-plan.md) | The session-by-session plan for that spec. |
| [course-repo-tickets.md](course-repo-tickets.md) | The eight tickets from that plan, with their checklists. |
| [sealed-pr-grading.md](sealed-pr-grading.md) | An earlier design: students submit an encrypted solution as a public pull request. Not built; the course-repo plan replaced it. |
| [faculty-authoring-prompt.md](faculty-authoring-prompt.md) | Design for a prompt faculty paste into any chat to turn a question into problem files. Approved, not yet written into the faculty guide. |

[../research/classroom50-architecture.md](../research/classroom50-architecture.md)
is background research on Classroom 50, which the course-repo design learned
from. No Classroom 50 code is copied.
