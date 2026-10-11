# GradBot Architecture

## How It Works (End to End)

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  CLI     │────▶│ Resolver │────▶│ Fetcher  │────▶│ Loader   │
│ cli.py   │     │resolver.py│    │fetcher.py│     │loader.py │
│          │     │          │     │          │     │          │
│ parse    │     │ slug →   │     │ git clone│     │ import   │
│ args     │     │ git URL  │     │ + fetch  │     │ checks.py│
│          │     │ + meta   │     │ (shallow)│     │ build DAG│
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                                       │
                      ┌────────────────┘
                      ▼
                 ┌──────────┐
                 │  Git     │
                 │ git.py   │
                 │          │
                 │ init     │
                 │ fetch    │
                 │ checkout │
                 └──────────┘
                                                        │
                                                        ▼
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Reporter │◀────│  Runner  │◀────│Compiler  │     │  API     │
│reporter.py│    │ runner.py│     │compiler.py│    │ api.py   │
│          │     │          │     │          │     │          │
│ render   │     │ execute  │     │ detect   │     │ run()    │
│ results  │     │ checks   │     │ language │     │ expect() │
│ + emoji  │     │ in order │     │ compile  │     │ helpers  │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
```

### Flow

1. **CLI** (`cli.py`): Parses command-line arguments, checks git availability
2. **Resolver** (`resolver.py`): Parses the slug and builds a git clone URL (HTTPS)
3. **Fetcher** (`fetcher.py`): Uses `git.py` to shallow-clone or update the problem repo
4. **Git** (`git.py`): Runs git CLI commands via subprocess (init, fetch, checkout, reset)
5. **Loader** (`loader.py`): Imports `checks.py`, collects decorated functions, builds dependency DAG
6. **Compiler** (`compiler.py`): Detects the student's language and compiles if needed
7. **Runner** (`runner.py`): Executes each check in topological order, each in an isolated temp dir
8. **API** (`api.py`): Provides `run()`, `expect_output()`, etc. that checks call
9. **Reporter** (`reporter.py`): Renders results with colors, a progress bar, hints, and a one-line score verdict

---

## Module Descriptions

### `result.py` — Data Types

The foundation. Defines `CheckResult` (single check outcome) and `SuiteResult` (aggregate). Pure dataclasses with JSON serialization. All other modules produce or consume these types.

### `resolver.py` — Slug Resolution

Parses `practice/arrays/two_sum[@v2]` into a public samples URL. `submit/...` does not build a clone URL and does not put a token in a git URL. Hidden grading goes through `gradbot.policy`: roster by numeric GitHub user id, one slot ref, zip checks, and a student payload with `cause` and `log` removed.

### `git.py` — Git CLI Wrapper

A thin wrapper around git commands via `subprocess`. Provides `run_git()` for low-level commands, `ensure_git_installed()` for early validation, and `clone_or_update()`, which shallow-clones with init, fetch --depth 1, checkout, and reset --hard.

### `workspace.py` — Working Area Utilities

`working_area()` copies files to a temp directory and cleans up on exit. `cd()` temporarily changes the working directory and restores it.

### `fetcher.py` — Git-Based Fetching

Uses `git.py` to shallow-clone problem repos from GitHub into `~/.gradbot/local/{owner}/{repo}/`. Updates via `git fetch` on each run. Falls back to stale local copy on network failure. Supports `--offline` mode using existing clones. Also provides `fetch_local()` for `--dev` mode.

### `compiler.py` — Language Detection & Compilation

Scans the solution directory for source files. Supports Python (syntax check), C (gcc), C++ (g++), and Java (javac). Extracts the first error and line number from compiler output and produces a short message like "Your code has an error on line 12."

### `api.py` — Check Author API

The public API that check suite authors use. Provides `run()` (execute student program via subprocess), `expect_output()` (exact/contains/regex matching), `expect_exit()`, `file_exists()`, and `expect_sequence()`. Uses thread-local context for the current check's working directory.

### `loader.py` — Check Discovery & DAG

Provides the `@gradbot.check()` decorator. Imports `checks.py` via `importlib`, collects decorated functions from a global registry, validates the dependency graph, and returns checks in topological order (Kahn's algorithm).

### `runner.py` — Check Execution

The engine. Runs each check in an isolated temp directory with a fresh copy of the student's files. Handles dependency skipping, timeout, and catches ALL exceptions. Compilation failure skips everything. Produces a `SuiteResult`.

### `reporter.py` — Terminal Output

The result screen. Unicode symbols (✓/✗/○), ANSI colors (with graceful degradation), block progress bars, and a score-based verdict. Practice mode shows details; submit mode shows only hints.

### `cli.py` — Command Line Interface

Argument parsing and top-level dispatch. Global exception handler ensures students never see a traceback. Supports `--dev` mode for local testing. Checks git availability before fetching.

---

## The Check Dependency DAG

Each check can optionally depend on another check. If a dependency fails, all its dependents are automatically skipped.

### Example

```python
@gradbot.check("Compiles correctly", points=0)
def test_compiles():
    ...

@gradbot.check("Basic case", depends_on="test_compiles", points=1)
def test_basic():
    ...

@gradbot.check("Edge case", depends_on="test_basic", points=1)
def test_edge():
    ...

@gradbot.check("Performance", depends_on="test_basic", points=1)
def test_performance():
    ...
```

This creates the DAG:

```
test_compiles
    └── test_basic
            ├── test_edge
            └── test_performance
```

If `test_basic` fails, both `test_edge` and `test_performance` are skipped.

### Topological Sort

Checks are sorted using Kahn's algorithm at load time. This guarantees:
- Every check runs after its dependency
- Cycles are detected and reported as errors
- Declaration order is preserved among independent checks
