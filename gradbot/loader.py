"""
Dynamic check discovery and loading for GradBot.

Reads ``suite.yaml``, imports ``checks.py`` via importlib, discovers all
functions decorated with ``@gradbot.check``, builds the dependency DAG,
and returns checks in topological order.
"""

from __future__ import annotations

import importlib.util
import sys
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from gradbot.errors import UserError

# ── @gradbot.check decorator ──────────────────────────────────────────

# Global registry populated during module import
_registered_checks: list[CheckFunction] = []


@dataclass
class CheckFunction:
    """A registered check function with its metadata."""

    func: Callable                      # the actual test function
    name: str                           # human-readable name
    slug: str                           # machine identifier (function name)
    depends_on: str | None = None       # slug of the dependency
    points: int = 1                     # points awarded on pass
    hint: str | None = None             # default hint on failure
    order: int = 0                      # declaration order


def check(
    name: str,
    depends_on: str | None = None,
    points: int = 1,
    hint: str | None = None,
):
    """
    Decorator that registers a function as a GradBot check.

    Args:
        name: Human-readable name shown in results (e.g. "Basic case works")
        depends_on: Name (slug) of another check that must pass first
        points: Points awarded when this check passes
        hint: Default hint to show on failure (can be overridden by CheckFailure.hint)

    Usage::

        @gradbot.check("Basic case works", points=1)
        def test_basic():
            result = gradbot.run(input="4\\n2 7 11 15\\n9\\n")
            gradbot.expect_output(result.stdout.strip(), "0 1")

        @gradbot.check("Handles negatives", depends_on="test_basic", points=1)
        def test_negatives():
            ...
    """

    def decorator(func: Callable) -> Callable:
        cf = CheckFunction(
            func=func,
            name=name,
            slug=func.__name__,
            depends_on=depends_on,
            points=points,
            hint=hint,
            order=len(_registered_checks),
        )
        _registered_checks.append(cf)
        # Attach metadata to the function for introspection
        func._gradbot_check = cf  # type: ignore[attr-defined]
        return func

    return decorator


# ── Suite config loading ──────────────────────────────────────────────


LANGUAGES = ("python", "c", "cpp", "java")
LANGUAGE_NAMES = {"python": "Python", "c": "C", "cpp": "C++", "java": "Java"}
DEFAULT_TIME_LIMIT = 5.0


@dataclass
class SuiteConfig:
    """Parsed suite.yaml configuration."""

    name: str = "Unnamed Problem"
    topic: str = "General"
    languages: list[str] = field(default_factory=lambda: list(LANGUAGES))
    time_limit: float = DEFAULT_TIME_LIMIT  # default timeout for gradbot.run()
    total_points: int = 0          # 0: not stated; dev warns if it disagrees with the checks
    general_hint: str = ""         # shown when a run misses marks
    raw: dict = field(default_factory=dict)  # the raw yaml dict


def load_suite_config(suite_dir: Path) -> SuiteConfig:
    """
    Load and parse ``suite.yaml`` from the given directory.

    Args:
        suite_dir: Path to the problem suite directory

    Returns:
        Parsed SuiteConfig

    Raises:
        LoadError: if suite.yaml is missing, is not valid YAML, or has the wrong shape
    """
    yaml_path = Path(suite_dir) / "suite.yaml"
    if not yaml_path.is_file():
        raise LoadError(f"Missing suite.yaml in {suite_dir}")

    try:
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, UnicodeDecodeError) as e:
        raise LoadError(f"suite.yaml in {suite_dir} is not valid YAML:\n  {e}") from e
    if not isinstance(raw, dict):
        raise LoadError(f"suite.yaml in {suite_dir} must be a mapping of keys, not a {type(raw).__name__}")

    problem = _section(raw, "problem", suite_dir)
    scoring = _section(raw, "scoring", suite_dir)
    hints = _section(raw, "hints", suite_dir)

    languages = problem.get("languages", list(LANGUAGES))
    if not isinstance(languages, list) or not languages:
        raise LoadError(f"problem.languages in suite.yaml ({suite_dir}) must be a list, such as [python, c]")
    unknown = [str(lang) for lang in languages if lang not in LANGUAGES]
    if unknown:
        raise LoadError(
            f"problem.languages in suite.yaml ({suite_dir}) lists {', '.join(unknown)}. "
            f"GradBot supports {', '.join(LANGUAGES)}."
        )

    time_limit = problem.get("time_limit", DEFAULT_TIME_LIMIT)
    if isinstance(time_limit, bool) or not isinstance(time_limit, (int, float)) or time_limit <= 0:
        raise LoadError(f"problem.time_limit in suite.yaml ({suite_dir}) must be a number of seconds above 0")

    total_points = scoring.get("total_points", 0)
    if isinstance(total_points, bool) or not isinstance(total_points, int) or total_points < 0:
        raise LoadError(f"scoring.total_points in suite.yaml ({suite_dir}) must be a whole number >= 0")

    return SuiteConfig(
        name=str(problem.get("name", "Unnamed Problem")),
        topic=str(problem.get("topic", "General")),
        languages=list(languages),
        time_limit=float(time_limit),
        total_points=total_points,
        general_hint=str(hints.get("general") or ""),
        raw=raw,
    )


def _section(raw: dict, key: str, suite_dir: Path) -> dict:
    """A top-level suite.yaml section. Missing or empty means defaults."""
    value = raw.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise LoadError(f"'{key}' in suite.yaml ({suite_dir}) must be a mapping of keys")
    return value


# ── Check loading and DAG construction ────────────────────────────────


class LoadError(UserError):
    """Raised when check loading or DAG construction fails."""
    pass


def load_checks(
    suite_dir: Path,
    checks_filename: str = "checks.py",
) -> tuple[SuiteConfig, list[CheckFunction]]:
    """
    Load checks from a problem suite directory.

    1. Reads suite.yaml
    2. Imports checks_filename (default checks.py) using importlib
    3. Collects all @gradbot.check-decorated functions
    4. Builds dependency DAG and validates it
    5. Returns checks in topological order

    Args:
        suite_dir: Path to the problem suite directory
        checks_filename: Check module filename inside suite_dir

    Returns:
        Tuple of (SuiteConfig, list of CheckFunction in execution order)

    Raises:
        LoadError: if the checks file can't be imported or the DAG is invalid
    """
    suite_dir = Path(suite_dir).resolve()

    # Load config
    config = load_suite_config(suite_dir)

    checks_path = suite_dir / checks_filename
    if not checks_path.exists():
        raise LoadError(f"Missing {checks_filename} in {suite_dir}")

    checks = _import_checks_module(checks_path)

    if not checks:
        raise LoadError(
            f"No checks found in {checks_path}.\n"
            f"Make sure your {checks_filename} has functions decorated with @gradbot.check()"
        )

    # Validate and sort
    ordered = _topological_sort(checks)

    return config, ordered


def guard_student_suite(suite_dir: Path) -> None:
    """Refuse a student-facing suite that still contains hidden checks."""
    hidden = Path(suite_dir) / "checks_hidden.py"
    if hidden.is_file():
        raise LoadError(f"checks_hidden.py must not be shipped in {suite_dir}")
    return None


_PUBLIC_BUNDLE_NAMES = ("suite.yaml", "statement.md", "checks.py")


def public_bundle_files(suite_dir: Path) -> list[Path]:
    """Existing public suite files. Never includes hidden checks or solutions."""
    suite_dir = Path(suite_dir)
    return [
        suite_dir / name
        for name in _PUBLIC_BUNDLE_NAMES
        if (suite_dir / name).is_file()
    ]


def _import_checks_module(checks_path: Path) -> list[CheckFunction]:
    """
    Import checks.py as a module and extract registered checks.

    Uses importlib to avoid exec() and ensure proper module semantics.
    """
    # Clear the global registry before importing
    _registered_checks.clear()

    # Create a unique module name to avoid conflicts
    module_name = f"_gradbot_checks_{id(checks_path)}"

    spec = importlib.util.spec_from_file_location(module_name, str(checks_path))
    if spec is None or spec.loader is None:
        raise LoadError(f"Could not create module spec for {checks_path}")

    module = importlib.util.module_from_spec(spec)

    # Make sure 'gradbot' is importable within the checks module
    # (it should be, since we're running from an installed package)
    old_path = sys.path.copy()
    old_dont_write = sys.dont_write_bytecode
    # No __pycache__ next to checks.py: the suite may be a git clone or a
    # faculty folder that gets published file by file.
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise LoadError(
            f"Error importing {checks_path.name}:\n  {type(e).__name__}: {e}\n"
            "Make sure the checks file is valid Python with correct gradbot imports."
        ) from e
    finally:
        sys.path = old_path
        sys.dont_write_bytecode = old_dont_write

    # Copy and clear the registry
    checks = list(_registered_checks)
    _registered_checks.clear()

    return checks


def _topological_sort(checks: list[CheckFunction]) -> list[CheckFunction]:
    """
    Sort checks in topological order (dependencies first).

    Uses Kahn's algorithm. Validates that:
    - All depends_on references point to existing checks
    - There are no cycles

    Returns:
        Checks in execution order (dependencies before dependents)

    Raises:
        LoadError: on invalid references or cycles
    """
    by_slug: dict[str, CheckFunction] = {}
    for c in checks:
        if c.slug in by_slug:
            raise LoadError(
                f"Two checks are both named '{c.slug}'. "
                "Give each @gradbot.check function its own name."
            )
        if not isinstance(c.points, int) or isinstance(c.points, bool) or c.points < 0:
            raise LoadError(f"Check '{c.slug}' has points={c.points!r}; points must be a whole number >= 0.")
        by_slug[c.slug] = c

    # Validate dependencies
    for c in checks:
        if c.depends_on is not None and c.depends_on not in by_slug:
            raise LoadError(
                f"Check '{c.slug}' depends on '{c.depends_on}', "
                f"but no check with that name exists.\n"
                f"Available checks: {', '.join(by_slug.keys())}"
            )

    # Build adjacency list and in-degree count
    # parent → list of children
    graph: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = {c.slug: 0 for c in checks}

    for c in checks:
        if c.depends_on is not None:
            graph[c.depends_on].append(c.slug)
            in_degree[c.slug] += 1

    # Kahn's algorithm
    # Start with all checks that have no dependencies, ordered by declaration
    queue = deque(
        sorted(
            [slug for slug, deg in in_degree.items() if deg == 0],
            key=lambda s: by_slug[s].order,
        )
    )
    ordered: list[CheckFunction] = []

    while queue:
        slug = queue.popleft()
        ordered.append(by_slug[slug])
        for child_slug in sorted(graph[slug], key=lambda s: by_slug[s].order):
            in_degree[child_slug] -= 1
            if in_degree[child_slug] == 0:
                queue.append(child_slug)

    if len(ordered) != len(checks):
        # Find the cycle
        remaining = {c.slug for c in checks} - {c.slug for c in ordered}
        raise LoadError(
            f"Circular dependency detected among checks: {', '.join(remaining)}\n"
            "Check the 'depends_on' values in your @gradbot.check() decorators."
        )

    return ordered
