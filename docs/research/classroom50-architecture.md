# Classroom 50 architecture (primary sources)

Research date: 2026-10-18. Sources are the local clones and the live GitHub README. There is no top-level `docs/` tree in the product repo; product documentation is the wiki (published from `wiki/` in the source repo) plus per-folder READMEs.

| Source | What was read |
| --- | --- |
| `C:\Users\chhav\AppData\Local\Temp\classroom50` | `origin` `https://github.com/foundation50/classroom50.git`, branch `main`, commit `48c1e9b0dafaecaf5312532c1a7fd40ce7de874d` (2026-10-14, `chore: release main (#1118)`) |
| `C:\Users\chhav\AppData\Local\Temp\classroom50-wiki` | `origin` `https://github.com/foundation50/classroom50.wiki.git`, branch `master`, commit `7ce8b082405dbe4fbd5211064388cfea10350555` (2026-10-14, `Sync from foundation50/classroom50@e268b5c`) |
| In-repo wiki vs wiki clone | Every file under `classroom50\wiki` hashes equal to the wiki clone (no content drift) |
| Live README | https://github.com/foundation50/classroom50 matches the cloned `README.md` |

`cloudflare_worker.js`, linked from the wiki as `https://github.com/foundation50/classroom50/blob/main/cloudflare_worker.js`, is not in the clone and returns 404 at `https://raw.githubusercontent.com/foundation50/classroom50/main/cloudflare_worker.js`. The client still calls a deployed worker. This note does not describe a worker implementation that is not in the tree.

## 1. What the product is

Classroom 50 is a free, GPLv3 tool from the Fifty Foundation for creating programming assignments, optional autograded correctness tests, and submission tracking on GitHub, positioned as an open-source alternative to GitHub Classroom ([README](https://github.com/foundation50/classroom50/blob/main/README.md), `C:\Users\chhav\AppData\Local\Temp\classroom50\README.md`, `C:\Users\chhav\AppData\Local\Temp\classroom50\LICENSE`, wiki `Home.md`). Teachers and students use either the static web app at https://classroom50.org or the `gh teacher` / `gh student` GitHub CLI extensions. It has no Classroom 50 server, database, or account system: the web app is a GitHub Pages site that runs in the browser, the CLIs run on the user's machine, and classrooms, rosters, assignments, scores, enrollment, and permissions are ordinary GitHub organization data plus files in a private `classroom50` repository in the teacher's organization (`C:\Users\chhav\AppData\Local\Temp\classroom50-wiki\Home.md`, `How-Classroom-50-Works.md`).

## 2. Wiki page map

Pages below are the Markdown files in `C:\Users\chhav\AppData\Local\Temp\classroom50-wiki` (same bytes as `C:\Users\chhav\AppData\Local\Temp\classroom50\wiki`). Titles are the H1 of each file. `_Sidebar.md` is navigation chrome, not a guide. `Home.md` also links two training PDFs under `slides/`; those are files, not wiki pages.

| Page | Purpose |
| --- | --- |
| [Home](https://github.com/foundation50/classroom50/wiki) (`Home.md`) | Product intro: what it is, web vs CLI, prerequisites, and links to training recordings. |
| Prerequisites and GitHub Education (`Prerequisites-and-GitHub-Education.md`) | Required GitHub account and Team/Enterprise organization, including the free teacher upgrade, plus school-network caveats. |
| How Classroom 50 Works (`How-Classroom-50-Works.md`) | Mental model: GitHub as the backend, roles, permissions, invites, grading flow, groups, and the service token. |
| Quickstart: your first classroom (`Quickstart.md`) | Shortest path from an empty organization to a graded assignment, web or CLI. |
| Web Teacher Guide (`Web-Teacher-Guide.md`) | End-to-end course setup and operation in the browser app. |
| CLI Teacher Guide (`CLI-Teacher-Guide.md`) | Same teacher walkthrough with `gh teacher`, from org creation through download. |
| Staff, TAs, and Multiple Teachers (`Staff-TAs-and-Multiple-Teachers.md`) | The four roles, what each can see, and one organization versus several. |
| Course Lifecycle and End of Term (`Course-Lifecycle-and-End-of-Term.md`) | Staging, due dates, mid-course starter updates, and end-of-term cleanup. |
| Autograding Basics (`Autograding-Basics.md`) | Grading modes, declarative tests, which commits grade, how to read scores, and feedback pull requests. |
| Autograder Recipes (`Autograder-Recipes.md`) | Ready-made declarative setups; the index page lists Python, Java, C#, C and C++, Rust, and bring-your-own CI (`Autograders.md`). |
| Advanced Autograding (`Advanced-Autograding.md`) | Custom `autograder.py`, the `result.json` contract, the `runtime` block, and replacing the runner. |
| Managing Actions Cost (`Managing-Actions-Cost.md`) | Who pays for Actions minutes, what a run costs, and how to reduce or cap spend. |
| Autograders (`Autograders.md`) | Redirect stub. The old single page was split into the four autograding pages above. |
| Web Student Guide (`Web-Student-Guide.md`) | Student path in the web app: join, sign in, accept, submit, view the score release. |
| CLI Student Guide (`CLI-Student-Guide.md`) | Student path with `gh student`: login, accept, clone, submit. |
| `gh teacher` reference (`gh-teacher.md`) | Every teacher CLI command and flag, including what `init` changes. |
| `gh student` reference (`gh-student.md`) | Every student CLI command and flag. |
| Installation (`Installation.md`) | Install, update, log in, and optionally build the two `gh` extensions. |
| Assignment Templates (`Assignment-Templates.md`) | Starter-code repos flagged as GitHub template repositories, and template-less shapes. |
| GitHub Integration (`GitHub-Integration.md`) | Manual GitHub steps, OAuth scopes, the proxy, privacy/FERPA, analytics, and the REST/workflow map. |
| Known Limitations (`Known-Limitations.md`) | Limits that follow from having no server, plus features the design does not support. |
| FAQ (`FAQ.md`) | Common questions, including plan, self-hosting, Actions, and the roadmap. |
| Troubleshooting (`Troubleshooting.md`) | Known errors and fixes, titled by the message you see. |
| Glossary (`Glossary.md`) | Canonical terms, including a GitHub Classroom vocabulary map. |
| Teacher Guide (`Teacher-Guide.md`) | Pointer only: start at Home, Quickstart, Web Teacher Guide, or CLI Teacher Guide. |
| `_Sidebar.md` | Wiki nav: start here, teacher guides, autograding, students, reference. |

## 3. Runtime architecture

Classroom 50 is three clients over one GitHub organization, plus GitHub Actions inside that organization. Nothing in the product keeps a classroom database (`How-Classroom-50-Works.md`).

```text
Browser SPA (classroom50.org or a self-built copy)
    |  localStorage token
    |  api.github.com  (almost all calls)
    |  Cloudflare Worker proxy (OAuth exchange + zip downloads only)
    v
GitHub organization
    classroom50 repo (private)  -- config, roster, scores, workflows
    GitHub Teams                -- enrollment and roles
    template repos              -- starter code
    student repos               -- submissions, Releases, feedback PRs
         |
         |  autograde.yaml calls reusable autograde-runner.yaml
         v
    GitHub Actions (setup + grade; collect / regrade / probe / publish-pages)

gh teacher / gh student on the teacher's or student's machine
    |  gh credential store, no proxy
    v
same GitHub organization and REST API
```

### Processes

| Process | Where it runs | Role |
| --- | --- | --- |
| Web app | Browser. Official hosting is GitHub Pages at `classroom50.org` (`web\CNAME`, `.github\workflows\web-deploy.yaml`). Preview is a separate repo, `foundation50/classroom50-web-preview`, at `preview.classroom50.org` (`.github\workflows\web-deploy-preview.yaml`) because one repo can have only one Pages custom domain. | React 19 + TypeScript + Vite SPA, TanStack Router/Query, Tailwind, daisyUI (`web\README.md`, `web\package.json` version `1.58.1`). No Classroom 50 backend. |
| `gh teacher`, `gh student` | User machine, as `gh` extensions. Go 1.26 modules using `github.com/cli/go-gh/v2` (`cli\gh-teacher\go.mod`, `cli\gh-student\go.mod`, `cli\README.md`, wiki `Installation.md`). | Same GitHub operations as the web app. Neither front end is primary (`How-Classroom-50-Works.md`). |
| Org workflows | Installed into the org's private `classroom50` repo by `gh teacher init` or web setup, from `cli\gh-teacher\skeleton\dotgithub\` (`cli\README.md`, wiki `gh-teacher.md`). | `publish-pages.yaml`, `collect-scores.yaml`, `regrade.yaml`, `probe-token.yaml`, reusable `autograde-runner.yaml`. |
| Student shim | `.github/workflows/autograde.yaml` committed at accept, unless the assignment opts out (`assignments-v1.schema.json` `no_autograder` / `empty_repo`). | Calls the reusable runner in the org `classroom50` repo (`autograde-runner.yaml` header). |
| GitHub proxy | Fifty Foundation Cloudflare Worker at `https://classroom50.fifty-foundation.workers.dev` unless `VITE_GITHUB_PROXY_BASE` is set (`web\src\github-core\workerProxy.ts`, wiki `GitHub-Integration.md`). | Only the OAuth token exchange (browser redirect and device flow) and repository zip downloads. CLIs never use it. |

Interactive work (create a classroom, invite, accept, save an assignment) runs at the moment a person does it, with their token. Background work (Pages publish, score collection, regrade, token probe) runs in Actions and needs the service token, not an open browser (`How-Classroom-50-Works.md`, `Advanced-Autograding.md` "No credentials required").

### Storage and data model

GitHub is the store (`How-Classroom-50-Works.md`):

| Concept | Stored as |
| --- | --- |
| Classroom metadata | `<classroom>/classroom.json` (`schema` `classroom50/classroom/v1`): name, slug, term, org, optional unlisted `secret`, optional `pages_base_url`, optional `active`, staff-team ids (`schemas\classroom-v1.schema.json`). |
| Assignments | `<classroom>/assignments.json` (`classroom50/assignments/v1`): slug, mode `individual` \| `group` (legacy) \| `team`, template, due, tests, runtime, feedback PR, lock/close, Pages, autograder flags (`schemas\assignments-v1.schema.json`). |
| Roster details GitHub cannot store | `<classroom>/roster.csv`. Columns: `github_id`, `username`, `email`, `first_name`, `last_name`, `name`, `section`, `role` (`Web-Teacher-Guide.md` "Roster CSV fields"). Enrollment itself is team membership, not the CSV (`How-Classroom-50-Works.md`). |
| Gradebook | `<classroom>/scores.json` (`classroom50/scores/v1`), written by `collect_scores.py`. Per assignment: graded `entries` (submissions newest first) or `detected` presence records when there is no autograde release (`schemas\scores-v1.schema.json`). |
| Group intent | `<classroom>/teams.json` (`classroom50/teams/v1`), a snapshot. Live push access is the GitHub Team (`schemas\teams-v1.schema.json`, `How-Classroom-50-Works.md`). |
| One submission | `result.json` (`classroom50/result/v1`) attached to a GitHub Release on tag `submit/<UTC-timestamp>-<short-sha>` (`schemas\result-v1.schema.json`, `Autograding-Basics.md`). |
| Accept marker | `.classroom50.yaml` in the student repo (`classroom50/repo-config/v1`): classroom, assignment, optional secret, owner login and numeric id (`schemas\repo-config-v1.schema.json`). Omitted for `no_autograder` and `empty_repo`. |
| Roles | GitHub teams, not a role table. Teacher = org owner on `classroom50-<classroom>-teacher`. Head TA = member on `-hta` (config-repo write). TA = member on `-ta` (config-repo read). Student = member on secret team `classroom50-<classroom>` (`How-Classroom-50-Works.md`, `Staff-TAs-and-Multiple-Teachers.md`). |
| Email invite before accept | Secret team `invite-<hash>` plus a pending `roster.csv` row. Sync deletes the team after accept (`How-Classroom-50-Works.md`). |
| Student repo name | `<classroom>-<assignment>-<username>`, lowercased. Team-mode group repo: `<classroom>-<assignment>-group-<n>`. Group team slug: `classroom50-group-<16-hex>-<n>` (`How-Classroom-50-Works.md`). |

Other JSON Schemas in `C:\Users\chhav\AppData\Local\Temp\classroom50\schemas`, not expanded here: `classroom-team-v1`, `group-team-v1`, `invite-v1`, `results-v1`, `tests-v1`.

What Pages publishes is an allow-list, and it is world-readable (or only obscured, for an unlisted classroom). `publish-pages.yaml` copies `runner.py`, `ensure_feedback_pr.py`, each `classroom.json` and `assignments.json`, default `autograder.py`, non-default `autograders/*.yaml`, and per-assignment `autograders/<slug>.tar.gz` (including materialized `tests.json`). It also writes `classrooms-index.json` with only `schema`, `name`, `short_name`, `term`, `org`, `active`, and `migrated_from`. Roster-only commits do not redeploy, and `roster.csv` is not in the allow-list. `scores.json` is not in the allow-list either, so the gradebook stays in the private repo and is read through the API. An unlisted `secret` only changes the URL path; the schema calls that obscurity, not access control (`publish-pages.yaml`, `classroom-v1.schema.json`).

Browser-only state: GitHub access token and UI preferences (`How-Classroom-50-Works.md`). Token keys are `gh_access_token`, `gh_client_id`, `gh_scope_granted`, `gh_auth_method` in `localStorage`; the PKCE verifier is `sessionStorage` for the OAuth round trip (`web\src\auth\constants.ts`, `web\src\auth\storage.ts`). Analytics consent, when present, is `classroom50:consent` (`web\README.md`). The CLI uses the `gh` credential store, not `GITHUB_TOKEN` (`GitHub-Integration.md`).

### Auth

Sign-in is a GitHub token. There is no Classroom 50 account (`GitHub-Integration.md`).

Web, normal path: GitHub OAuth app, PKCE. The public client id is build-time `VITE_GITHUB_CLIENT_ID` (a repository variable, not a secret). The browser sends the code and `code_verifier` to the proxy routes `/web/token`, `/device/code`, and `/device/token`. The proxy holds the OAuth client secret and calls GitHub, because the token endpoint has no CORS headers (`web\README.md`, `web\src\auth\github-oauth-api.ts`, `workerProxy.ts`, `GitHub-Integration.md`). Production callback is `https://classroom50.org/login` (`web\README.md`).

Web, no proxy: paste a classic or fine-grained personal access token. Those calls go straight to `api.github.com` (`GitHub-Integration.md`). A fine-grained token is the only way to limit the grant to one organization; classic `repo` is all repositories (`Known-Limitations.md`).

CLI: `gh teacher login` and `gh student login` both run `gh auth login` with `admin:org`, `read:org`, `repo`, and `workflow`. `delete_repo` is not requested unless the teacher opts in for organization teardown (`GitHub-Integration.md`, `web\src\auth\constants.ts`). One scope set is shared because one person can be both teacher and student. After sign-in, capabilities follow org and team membership, not the extra scopes a student cannot exercise (`GitHub-Integration.md`).

Service token: one fine-grained PAT per organization, secret `CLASSROOM50_SERVICE_TOKEN` on the `classroom50` repo. Resource owner is the teaching org, all repositories, contents/actions/workflows/administration read-write, metadata read, org members read. Used only by collect, regrade, and probe. The web app can also store expiry and display name as Actions variables; the CLI does not (`GitHub-Integration.md`). Uploads are encrypted with libsodium before they are stored (`GitHub-Integration.md`; `libsodium-wrappers` is a web dependency in `web\package.json`). Students never configure tokens for grading: the grade job uses the job `GITHUB_TOKEN` plus unauthenticated Pages fetches (`Advanced-Autograding.md`).

Organization lockdown at setup sets base permission to none and disables member powers such as repo deletion, transfer, and visibility changes, while leaving private-repo creation, public Pages creation, and team creation on (`How-Classroom-50-Works.md`, `GitHub-Integration.md`, `gh-teacher.md`). Two org rulesets protect the default branch history and the frozen `feedback` branch. Four member-privilege settings have no API, so `init` cannot set them (`GitHub-Integration.md`).

### Grading

1. The student pushes, or runs `gh student submit`, depending on submission type `every-push` or tagged commit (`Autograding-Basics.md`, `Managing-Actions-Cost.md`).
2. The student repo's `autograde.yaml` calls reusable `autograde-runner.yaml`. That file splits work into two jobs because `runs-on` must be known before the grade job starts: `setup` on `ubuntu-latest`, then `grade` on the assignment's runner (`autograde-runner.yaml`, `GitHub-Integration.md`).
3. `setup` fetches `https://<org>.github.io/classroom50/runner.py` (or the org's custom Pages domain) and reads the assignment runtime from the published `assignments.json`.
4. `grade` runs `runner.py`, which runs declarative tests and/or `autograder.py` (per-assignment bundle, else classroom default, else a vacuous pass). Default host runtime is `ubuntu-latest` and Python 3.14. Optional `runtime` fields select runner labels, language versions, apt packages, or a public container image (`Advanced-Autograding.md`, `Autograding-Basics.md`).
5. A pass or fail publishes a Release (score, per-test table, `result.json`) and a `classroom50/autograde` commit status. An infrastructure `error` does not move the Release (`Advanced-Autograding.md`). The grade job stops after 15 minutes.
6. A teacher runs `collect-scores.yaml` (web **Collect now** / **Collect all**, or `workflow_dispatch`). It walks releases with the service token and commits `scores.json`. Due dates mark rows `late`; they do not block submission (`assignments-v1.schema.json`, `Autograding-Basics.md`).
7. Optional feedback pull request: opened at accept, base frozen at the accept commit, staff exempt from the ruleset so they can merge (`How-Classroom-50-Works.md`, `Autograding-Basics.md`).

Grading modes on the assignment: not graded, autograded, or manual score entry. **Do not use the built-in autograder** installs no Classroom 50 workflow; collection then records submitters without scores (`Autograding-Basics.md`). An example CS50 adapter under `examples\autograders\cs50\` is not part of the default pipeline: it runs `check50 --local` inside the public image `cs50/cli` (`examples\autograders\cs50\README.md`, `runtime.json`).

Scores are not shown inside the student web app. The student opens the Release. The wiki says the browser cannot read Release assets cross-origin (`FAQ.md`, issue https://github.com/foundation50/classroom50/issues/567).

### Hosting of the official app

Production Pages deploys when a `web-v*` release is cut; `.github\workflows\web-deploy.yaml` is a manual redeploy of `web/dist` plus a `404.html` SPA fallback, because GitHub Pages has no SPA rewrites. The OAuth client id and optional proxy base are Actions variables. Analytics variables are applied only in that deploy path (`web-deploy.yaml`, `web\README.md`, `web\vite\analytics.ts`). The product itself, once a teacher has run setup, is hosted entirely in the teacher's GitHub organization (`Home.md`, `FAQ.md`).

## 4. External dependencies: free-tier vs paid

Nothing in these sources names a Classroom 50 subscription, a license key, or a paid API sold by the Fifty Foundation. The software license is GPLv3 (`LICENSE`, `README.md`). Costs that do appear are GitHub plan and GitHub Actions, plus optional third parties used only by the hosted website.

| Dependency | Required? | What the sources say about cost |
| --- | --- | --- |
| GitHub account | Yes | Students can use the free plan (`Prerequisites-and-GitHub-Education.md`). |
| GitHub organization on Team or Enterprise | Yes for a normal classroom | Free organizations can be created, but Free cannot serve Pages from the private `classroom50` repo, and the FAQ says free/personal organizations cannot host a classroom (`Prerequisites-and-GitHub-Education.md`, `FAQ.md` "Do I need a paid GitHub plan?", `Web-Teacher-Guide.md`). Verified teachers can upgrade the org to Team at no cost through GitHub Education (`Home.md`, `Prerequisites-and-GitHub-Education.md`). The sources do not state a dollar price for Team or Enterprise. |
| Plan slugs the code treats as private-Pages-capable | Implementation detail | CLI: `team`, `business`, `business_plus`, `enterprise` (`cli\gh-teacher\init_repo.go`). A `free` plan is an advisory warning, not a hard `init` failure: the repo is still created but `publish-pages` may not deploy (`init_preflight.go`). Web setup blocks only `plan.name == "free"` with **Not supported**; `team` and `enterprise` are "supported"; any other name is "unknown" and still offered **Set up** (`web\src\lib\orgPlan.ts`, `NewOrgModal.tsx`). |
| GitHub Enterprise Server | Optional, not the hosted app | Wiki: private-repo Pages exists on Enterprise Server, and `collect_scores.py` honors `GITHUB_API_URL` for Enterprise Server (`GitHub-Integration.md`). The FAQ says the product does not integrate with self-hosted Git platforms other than GitHub (`FAQ.md`). The web client defaults to `https://api.github.com` (`web\src\github-core\client.ts`). |
| GitHub Actions minutes | Yes if you use the built-in autograder on private repos | The organization is billed, never the student. Wiki: Team includes 3,000 minutes/month; past that, usage is billed up to the spending limit. Each grading run is two jobs and bills at least about two minutes. Public standard-runner minutes are free, but a public student repo cannot run the workflow in the private `classroom50` repo, so public visibility does not make built-in autograding free (`Managing-Actions-Cost.md`). The web gradebook's quota map, commented as copied from GitHub's billing docs on 2026-07-22 and not exposed by the API, is free 2000, pro 3000, team 3000, business 50000, enterprise 50000 (`web\src\github-core\queries\billingReads.ts`). Treat that map as the app's assumption, not a live price check. |
| $0 Actions spending cap | Created by setup when the org has none | Stops paid overage; when included minutes are gone, runs are blocked until the next billing month or the cap is raised. A cap you already set is not modified. Enterprise billing often cannot be read (`Managing-Actions-Cost.md`, `gh-teacher.md`). |
| Self-hosted Actions runners | Optional replacement for hosted minutes | Grading on your own labels costs no GitHub Actions minutes. You must supply bash, curl, python3, pip, `gh`, and ideally git. The sources do not price the hardware (`Managing-Actions-Cost.md`, `Advanced-Autograding.md`, `FAQ.md`). |
| Fine-grained PAT (service token) and user OAuth/PAT | Yes for background jobs; yes for sign-in | GitHub tokens. No separate token vendor (`GitHub-Integration.md`). |
| GitHub Pages | Yes for the grading manifest | Public Pages on the private `classroom50` repo. That feature is why Team/Enterprise is required (`GitHub-Integration.md`, `Prerequisites-and-GitHub-Education.md`). On GitHub Free, a student repo can have Pages only if the repo is public, and then it cannot use the built-in autograder: "Pages or autograding, not both" (`GitHub-Integration.md`). |
| Fifty Foundation Cloudflare Worker | Only for web OAuth and in-app zip download | Default host `classroom50.fifty-foundation.workers.dev`. Stateless; holds the OAuth client secret (`GitHub-Integration.md`, `workerProxy.ts`). The sources do not state a Cloudflare bill. PAT sign-in and both CLIs avoid it. |
| Google Tag Manager / GA4 and Cloudflare Web Analytics | No | Injected only when `VITE_GTM_CONTAINER_ID` or `VITE_CF_BEACON_TOKEN` is set, and only on the official production and preview deploys. Consent-gated. CLIs send nothing. Self-hosted builds have no tracking unless you set the variables (`web\vite\analytics.ts`, `web\README.md`, `GitHub-Integration.md`). |
| `www.githubstatus.com` | No | Best-effort outage banner (`GitHub-Integration.md`). |
| PyPI packages used at grade time | Only when that path runs | `pyyaml` in the setup job; `pytest` and `pytest-json-report` installed on demand by `runner.py` (`autograde-runner.yaml`, `Advanced-Autograding.md`). No paid registry is named. |
| Public container images | Only if `runtime.container` is set | Must be publicly pullable. Private registry pull secrets are unsupported. Example image `cs50/cli:latest` (`Advanced-Autograding.md`, `examples\autograders\cs50\runtime.json`). |
| check50 | Only the CS50 example | Upstream https://github.com/cs50/check50, not the default grader (`examples\autograders\cs50\README.md`). |
| GitHub Codespaces | No | If the org enables it, students may open their repo there. Classroom 50 does not manage Codespaces or its education benefit (`FAQ.md`). |
| GitHub CLI, Git, Go (build only), Node (web build only) | CLI needs `gh`; web build needs Node | Install docs name `gh` and, for source builds, Go (`Installation.md`). Web dev needs Node/npm (`web\README.md`). |
| Training video hosts | No | YouTube and `time.cs50.io` are linked from `Home.md` only. |

Org invitation rate limits are GitHub's: 50 per day if the org is under a month old or on the free plan, otherwise 500 (`Web-Teacher-Guide.md`). LTI/LMS passback is not implemented; CSV and `scores.json` are the export path (`Known-Limitations.md`, `FAQ.md`).

## 5. What a $0 self-host would keep, drop, or replace

The FAQ answer to self-hosting is that there is no server to host: the product runs on GitHub, and you may host your own copy of the static web app. It will not talk to a non-GitHub forge (`FAQ.md` "Can I self-host Classroom 50?"). "Self-host" here means your own copy of the clients. Classroom state still lives in a GitHub organization.

A full teaching loop at $0, as these sources describe it, still depends on GitHub not charging that organization: Team via GitHub Education (or an existing Enterprise entitlement), and Actions usage inside the included minutes or on self-hosted runners, with the default $0 overage cap left in place so a spike blocks runs instead of billing (`Prerequisites-and-GitHub-Education.md`, `Managing-Actions-Cost.md`, `gh-teacher.md`). The sources never quote a Team subscription price, so an org that cannot get Team or Enterprise without paying is not a $0 deployment. Without that plan, private `classroom50` Pages (the manifest the runner fetches) is the feature that fails (`init_preflight.go`, `FAQ.md`).

### Keep

- The data model: private `classroom50` repo, teams, template repos, student repos, Releases, rulesets, service token (`How-Classroom-50-Works.md`).
- Both CLIs, installed from `foundation50/gh-teacher` and `foundation50/gh-student` or built from the GPLv3 tree (`Installation.md`, `LICENSE`). They need no proxy, no analytics, and no Fifty Foundation host (`GitHub-Integration.md`).
- Built-in autograding, declarative tests, custom `autograder.py`, feedback PRs, and score collection, as long as Actions minutes or self-hosted runners are available (`Autograding-Basics.md`, `Managing-Actions-Cost.md`).
- Web UI behavior if you build `web/` yourself. `npm run dev` / `npm run build` do not inject analytics unless you set the `VITE_*` vendor variables (`web\vite\analytics.ts`).
- Student accounts on GitHub Free (`Prerequisites-and-GitHub-Education.md`).
- PAT sign-in, which never contacts the proxy (`GitHub-Integration.md`).

### Drop

- https://classroom50.org and https://preview.classroom50.org. Those are the project's Pages deploys (`web-deploy.yaml`, `web-deploy-preview.yaml`), not required once you have a build or you use only the CLI (`FAQ.md`, `Home.md`).
- Google Tag Manager, Google Analytics, and Cloudflare Web Analytics (`web\vite\analytics.ts`, `GitHub-Integration.md`).
- The Fifty Foundation worker, if every user signs in with a PAT and you do not need in-app zip downloads (`GitHub-Integration.md`).
- The CS50 `check50` / `cs50/cli` example (`examples\autograders\cs50\README.md`).
- Codespaces (`FAQ.md`).
- YouTube / training slides (`Home.md`).

### Replace

| Official piece | $0 replacement the sources actually describe | What you lose if you do not replace it |
| --- | --- | --- |
| Hosted SPA | Any static file host, including your own GitHub Pages site. Build with Node. Set `VITE_GITHUB_CLIENT_ID` for OAuth. Deep links need the same `404.html` copy the deploy workflow makes, or equivalent (`web\README.md`, `web-deploy.yaml`). | Nothing functional if the files are served and users can reach GitHub. |
| OAuth proxy | Your own proxy, base URL `VITE_GITHUB_PROXY_BASE` (https, or localhost in dev). Client routes are `POST /web/token`, `POST /device/code`, `POST /device/token`, and `GET /repos/{owner}/{repo}/zipball[/{ref}]` (`workerProxy.ts`, `github-oauth-api.ts`, `client.ts`, `GitHub-Integration.md`). The wiki points at `cloudflare_worker.js` for the source, but that file is not on `main` (404, 2026-10-18), so this tree does not contain a worker you can copy. | Browser **Sign in with GitHub** and device-code sign-in, and in-app repo downloads. PAT sign-in still works with no proxy. |
| GitHub-hosted graders | Assignment `runs-on` set to your self-hosted labels. Image must include the grade-job tools (`Advanced-Autograding.md`). | Included-minute burn. You take on the runner machine yourself; the sources do not call that a GitHub charge. |
| Team plan via Education | No in-product substitute. Public student repos do not unlock the private-repo runner (`Managing-Actions-Cost.md`). CLI `init` on a free plan is only a warning (`init_preflight.go`). | Publishing `assignments.json` and `runner.py` from the private config repo, which is how grading is configured. |
| Actions overage | Leave the $0 cap. Pause grading, grade on submit tags only, or turn the built-in autograder off (`Managing-Actions-Cost.md`). | Runs past the included minutes stop until the cap is raised or the next month starts. Raising the cap is the paid path. |

CLI-only operation is the smallest $0 footprint that these sources support: no static host, no OAuth app, no proxy, no analytics, and the same GitHub org, Actions, and service token the web app would use (`FAQ.md`, `Installation.md`, `How-Classroom-50-Works.md`).
