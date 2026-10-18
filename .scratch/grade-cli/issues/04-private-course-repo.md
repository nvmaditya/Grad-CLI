# 04 — Private course repository

**What to build:** A teacher can ask Grade CLI to create a private `gradecli` repository and set the Actions spending cap to zero dollars. If GitHub hides billing, setup says so and still finishes. No Pages site is enabled.

**Blocked by:** 03 — Stage the course tree

**Status:** ready-for-agent

- [ ] The create-repository call is private and named `gradecli`.
- [ ] No request URL contains `/pages`.
- [ ] A spending cap of zero returns set on success and advisory on 403.
