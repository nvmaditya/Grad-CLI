# 01 — Roster rows and assignment tests

**What to build:** A teacher can add a student to a classroom roster and attach a named test to an assignment. A duplicate student or a duplicate test name is refused. The classroom stays on the free plan with Pages off.

**Blocked by:** None — can start immediately.

**Status:** done

- [x] A roster row records the GitHub id, username, and role `student` in the seven-column CSV.
- [x] The same GitHub id cannot be added twice.
- [x] An assignment test stores name, type, and points, and the classroom file still says the free plan and Pages off.
- [x] A second test with the same name is refused.
- [x] `grade course roster-add` and `grade assignment test-add` do the same writes.
