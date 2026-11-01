"""
Language detection and compilation for GradBot.

Supports Python, C, C++, and Java. Compilation errors are translated
into short student-facing messages — raw compiler output is only shown with ``--verbose``.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from gradbot.errors import UserError
from gradbot.sandbox import JAVA_RELEASE


@dataclass(slots=True)
class CompileResult:
    """Result of compiling a student's solution."""

    success: bool
    language: str
    binary_path: str | None = None        # path to the compiled binary / main script
    error_output: str = ""                 # raw compiler error output
    friendly_error: str = ""               # student-facing error message
    source_files: list[str] = field(default_factory=list)


# ── File extension → language mapping ──────────────────────────────────
_EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".java": "java",
}

# Priority order when multiple languages are found
_LANGUAGE_PRIORITY = ["python", "c", "cpp", "java"]


def detect_language(solution_dir: Path) -> str | None:
    """
    Detect the programming language from files in the solution directory.

    Scans for source files and returns the most likely language.
    If multiple languages are found, follows priority order.

    Args:
        solution_dir: Path to the directory containing the student's code

    Returns:
        Language string ("python", "c", "cpp", "java") or None
    """
    found_languages: set[str] = set()

    for file in solution_dir.iterdir():
        if file.is_file():
            ext = file.suffix.lower()
            if ext in _EXTENSION_MAP:
                found_languages.add(_EXTENSION_MAP[ext])

    if not found_languages:
        return None

    # Return highest priority language found
    for lang in _LANGUAGE_PRIORITY:
        if lang in found_languages:
            return lang

    return None


def _find_source_files(solution_dir: Path, language: str) -> list[Path]:
    """Find all source files for a given language in the solution directory."""
    ext_map = {
        "python": [".py"],
        "c": [".c"],
        "cpp": [".cpp", ".cc", ".cxx"],
        "java": [".java"],
    }
    extensions = ext_map.get(language, [])
    files: list[Path] = []
    for ext in extensions:
        files.extend(solution_dir.glob(f"*{ext}"))
    return sorted(files)


def _extract_friendly_error(raw_error: str, language: str) -> str:
    """
    Extract a student-facing error message from raw compiler output.

    Tries to find the first error and its line number, then wraps it
    in a short message.
    """
    if not raw_error.strip():
        return "Something went wrong during compilation, but there's no error message."

    lines = raw_error.strip().splitlines()

    # Try to extract first error with line number
    line_num = None
    error_msg = None

    if language in ("c", "cpp"):
        # GCC/Clang format: file.c:12:5: error: ...
        for line in lines:
            match = re.match(r".*?:(\d+):\d*:?\s*error:\s*(.+)", line)
            if match:
                line_num = match.group(1)
                error_msg = match.group(2).strip()
                break
    elif language == "java":
        # javac format: file.java:12: error: ...
        for line in lines:
            match = re.match(r".*?:(\d+):\s*error:\s*(.+)", line)
            if match:
                line_num = match.group(1)
                error_msg = match.group(2).strip()
                break
    elif language == "python":
        # Python syntax error: SyntaxError on line N
        for line in lines:
            match = re.search(r"line\s+(\d+)", line, re.IGNORECASE)
            if match:
                line_num = match.group(1)
                # The actual error is typically the last line
                error_msg = lines[-1].strip() if lines else None
                break

    if line_num and error_msg:
        return (
            f"Hmm, your code has an error on line {line_num}.\n"
            f"The compiler says: {error_msg}\n"
            f"Check that line and try again!"
        )
    elif line_num:
        return (
            f"Hmm, your code has an error on line {line_num}.\n"
            f"Check that line and try again!"
        )
    else:
        # Fallback — just show a summary
        first_line = lines[0] if lines else "Unknown error"
        return (
            f"Your code couldn't compile.\n"
            f"Here's a clue: {first_line}\n"
            f"Double-check your code for typos or missing brackets!"
        )


def compile_solution(
    solution_dir: Path, language: str | None = None, for_docker: bool = False,
) -> CompileResult:
    """
    Compile the student's solution.

    Args:
        solution_dir: Path to the directory containing the student's code
        language: Override language detection (if None, auto-detect)
        for_docker: Build for the sandbox images: link C/C++ statically (Linux
            only) and compile Java for the image's JRE (``--release``)

    Returns:
        CompileResult with success status, binary path, and error info
    """
    solution_dir = Path(solution_dir).resolve()

    if language is None:
        language = detect_language(solution_dir)
        if language is None:
            return CompileResult(
                success=False,
                language="unknown",
                friendly_error=(
                    "GradBot couldn't find any code to check!\n"
                    "Make sure your solution file is in the current directory.\n"
                    "Supported file types: .py, .c, .cpp, .java"
                ),
            )

    source_files = _find_source_files(solution_dir, language)
    if not source_files:
        return CompileResult(
            success=False,
            language=language,
            friendly_error=(
                f"GradBot found no {language} source files in this directory.\n"
                "Make sure your solution file is here and has the right extension."
            ),
        )

    source_names = [f.name for f in source_files]

    # ── Dispatch to language-specific compilation ──────────────────
    if language == "python":
        return _compile_python(solution_dir, source_files, source_names)
    elif language == "c":
        return _compile_c(solution_dir, source_files, source_names, for_docker)
    elif language == "cpp":
        return _compile_cpp(solution_dir, source_files, source_names, for_docker)
    elif language == "java":
        return _compile_java(solution_dir, source_files, source_names, for_docker)
    else:
        return CompileResult(
            success=False,
            language=language,
            friendly_error=f"GradBot doesn't know how to compile {language} files yet.",
        )


# A folder with several .py files runs the first of these that exists.
_PYTHON_ENTRY_NAMES = ("solution.py", "main.py")


def _python_entry_point(source_files: list[Path]) -> Path | None:
    """Pick the file to run: solution.py, main.py, the only file, or the only __main__ guard."""
    by_name = {f.name: f for f in source_files}
    for name in _PYTHON_ENTRY_NAMES:
        if name in by_name:
            return by_name[name]
    if len(source_files) == 1:
        return source_files[0]
    guarded = [
        f for f in source_files
        if "__main__" in f.read_text(encoding="utf-8", errors="replace")
    ]
    if len(guarded) == 1:
        return guarded[0]
    return None


def _compile_python(
    solution_dir: Path, source_files: list[Path], source_names: list[str]
) -> CompileResult:
    """Syntax-check Python files with the built-in compile(). Writes nothing to disk."""
    main_file = _python_entry_point(source_files)
    if main_file is None:
        return CompileResult(
            success=False,
            language="python",
            friendly_error=(
                f"GradBot found several Python files ({', '.join(source_names)}) "
                "and doesn't know which one to run.\n"
                "Name the file to run solution.py (or main.py)."
            ),
            source_files=source_names,
        )

    errors = []
    for src in source_files:
        try:
            compile(src.read_bytes(), src.name, "exec", dont_inherit=True)
        except (SyntaxError, ValueError) as e:
            # ValueError: null bytes in the source on Python < 3.12.
            errors.append("".join(traceback.format_exception_only(type(e), e)).rstrip())

    if errors:
        raw = "\n".join(errors)
        return CompileResult(
            success=False,
            language="python",
            error_output=raw,
            friendly_error=_extract_friendly_error(raw, "python"),
            source_files=source_names,
        )

    return CompileResult(
        success=True,
        language="python",
        binary_path=str(main_file),
        source_files=source_names,
    )


def _compile_c(
    solution_dir: Path, source_files: list[Path], source_names: list[str], static: bool = False
) -> CompileResult:
    """Compile C files using gcc."""
    output_binary = solution_dir / "solution"
    if os.name == "nt":
        output_binary = solution_dir / "solution.exe"

    cmd = [
        "gcc",
        *[str(f) for f in source_files],
        "-o", str(output_binary),
        "-lm",
        *(["-static"] if static else []),
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(solution_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return CompileResult(
            success=False,
            language="c",
            friendly_error=(
                "GradBot couldn't find the C compiler (gcc).\n"
                "Ask your teacher to install GCC on this computer."
            ),
            source_files=source_names,
        )
    except subprocess.TimeoutExpired:
        return CompileResult(
            success=False,
            language="c",
            friendly_error="Compilation took too long — that shouldn't happen!",
            source_files=source_names,
        )

    if result.returncode != 0:
        raw = result.stderr
        return CompileResult(
            success=False,
            language="c",
            error_output=raw,
            friendly_error=_extract_friendly_error(raw, "c"),
            source_files=source_names,
        )

    return CompileResult(
        success=True,
        language="c",
        binary_path=str(output_binary),
        source_files=source_names,
    )


def _compile_cpp(
    solution_dir: Path, source_files: list[Path], source_names: list[str], static: bool = False
) -> CompileResult:
    """Compile C++ files using g++."""
    output_binary = solution_dir / "solution"
    if os.name == "nt":
        output_binary = solution_dir / "solution.exe"

    cmd = [
        "g++",
        *[str(f) for f in source_files],
        "-o", str(output_binary),
        "-std=c++17",
        *(["-static"] if static else []),
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(solution_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return CompileResult(
            success=False,
            language="cpp",
            friendly_error=(
                "GradBot couldn't find the C++ compiler (g++).\n"
                "Ask your teacher to install G++ on this computer."
            ),
            source_files=source_names,
        )
    except subprocess.TimeoutExpired:
        return CompileResult(
            success=False,
            language="cpp",
            friendly_error="Compilation took too long — that shouldn't happen!",
            source_files=source_names,
        )

    if result.returncode != 0:
        raw = result.stderr
        return CompileResult(
            success=False,
            language="cpp",
            error_output=raw,
            friendly_error=_extract_friendly_error(raw, "cpp"),
            source_files=source_names,
        )

    return CompileResult(
        success=True,
        language="cpp",
        binary_path=str(output_binary),
        source_files=source_names,
    )


def _compile_java(
    solution_dir: Path, source_files: list[Path], source_names: list[str], for_docker: bool = False
) -> CompileResult:
    """Compile Java files using javac; for Docker, for the image's JRE."""
    release = ["--release", str(JAVA_RELEASE)] if for_docker else []
    cmd = ["javac", *release, *[str(f) for f in source_files]]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(solution_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return CompileResult(
            success=False,
            language="java",
            friendly_error=(
                "GradBot couldn't find the Java compiler (javac).\n"
                "Ask your teacher to install the JDK on this computer."
            ),
            source_files=source_names,
        )
    except subprocess.TimeoutExpired:
        return CompileResult(
            success=False,
            language="java",
            friendly_error="Compilation took too long — that shouldn't happen!",
            source_files=source_names,
        )

    too_old = re.search(r"release version \d+ not supported", result.stderr)
    if result.returncode != 0 and for_docker and too_old:
        # The grader's JDK is too old; the student's code never reached the compiler.
        raise UserError(
            f"Grading Java in the Docker sandbox needs JDK {JAVA_RELEASE} or newer on this "
            f"machine: javac {' '.join(release)} failed with: {result.stderr.splitlines()[0]}"
        )

    if result.returncode != 0:
        raw = result.stderr
        return CompileResult(
            success=False,
            language="java",
            error_output=raw,
            friendly_error=_extract_friendly_error(raw, "java"),
            source_files=source_names,
        )

    # Find the main class — look for a class with main method
    main_class = _find_java_main_class(solution_dir, source_files)

    return CompileResult(
        success=True,
        language="java",
        binary_path=main_class,
        source_files=source_names,
    )


def _find_java_main_class(solution_dir: Path, source_files: list[Path]) -> str | None:
    """Find the Java class containing the main method."""
    for src in source_files:
        content = src.read_text(encoding="utf-8", errors="replace")
        if re.search(r"public\s+static\s+void\s+main\s*\(", content):
            return src.stem  # Class name = filename without .java
    # Fallback: use first file
    if source_files:
        return source_files[0].stem
    return None


_DISPLAY = {"python": "Python", "c": "C", "cpp": "C++", "java": "Java"}


def _join(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def restrict_languages(compile_result: CompileResult, allowed: list[str]) -> CompileResult:
    """Turn a successful build in a language the problem doesn't accept into a failure."""
    if not compile_result.success or compile_result.language in allowed:
        return compile_result
    found = _DISPLAY.get(compile_result.language, compile_result.language)
    files = ", ".join(compile_result.source_files)
    return CompileResult(
        success=False,
        language=compile_result.language,
        friendly_error=(
            f"This problem accepts {_join([_DISPLAY.get(a, a) for a in allowed])}. "
            f"Your folder has {found} ({files})."
        ),
        source_files=compile_result.source_files,
    )


def get_run_command(compile_result: CompileResult) -> list[str]:
    """
    Get the command to run the compiled student solution.

    Args:
        compile_result: The result from compile_solution()

    Returns:
        Command as a list of strings suitable for subprocess.run()
    """
    if not compile_result.success or not compile_result.binary_path:
        return []

    lang = compile_result.language

    if lang == "python":
        # The interpreter running GradBot, not whatever `python` is on PATH:
        # pipx installs, Homebrew and stock Ubuntu have no `python` at all.
        return [sys.executable, compile_result.binary_path]
    elif lang in ("c", "cpp"):
        return [compile_result.binary_path]
    elif lang == "java":
        return ["java", compile_result.binary_path]
    else:
        return []
