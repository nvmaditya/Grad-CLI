# 02 — Grade workflow text

**What to build:** The course grade workflow checks out the course and one student commit, then runs the existing grader. It never mentions GitHub Pages. The faculty token is cleared before the student program starts.

**Blocked by:** 01 — Roster rows and assignment tests

**Status:** ready-for-agent

- [ ] The workflow text contains no Pages host.
- [ ] The checkout of the student commit is the only step that names the faculty token.
- [ ] The grade step clears the faculty token, `GITHUB_TOKEN`, and `GRADBOT_APP_TOKEN` before the grader runs.
