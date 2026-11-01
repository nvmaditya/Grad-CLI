"""
Integration tests for GradBot.

End-to-end tests using the local sample problem suites — no network needed.
These tests verify the complete pipeline: load → compile → run → render.
"""

import io
from pathlib import Path

from gradbot.compiler import compile_solution
from gradbot.loader import load_checks
from gradbot.reporter import render
from gradbot.runner import run_suite

# Path to the problems directory
PROBLEMS_DIR = Path(__file__).parent.parent / "problems"


def _run_problem_e2e(problem_path: str, solution_subdir: str = "sample_solution"):
    """Run a full end-to-end check on a problem with its sample solution."""
    suite_dir = PROBLEMS_DIR / problem_path
    solution_dir = suite_dir / solution_subdir

    assert suite_dir.exists(), f"Suite dir not found: {suite_dir}"
    assert solution_dir.exists(), f"Solution dir not found: {solution_dir}"

    # Load checks
    config, checks = load_checks(suite_dir)
    assert len(checks) >= 4, f"Expected at least 4 checks, got {len(checks)}"

    # Compile
    compile_result = compile_solution(solution_dir)
    assert compile_result.success, (
        f"Sample solution failed to compile: {compile_result.friendly_error}"
    )

    # Run
    suite_result = run_suite(config, checks, solution_dir, compile_result, "practice")

    # Render (to verify no crashes)
    buf = io.StringIO()
    render(suite_result, stream=buf, no_color=True)
    output = buf.getvalue()

    return suite_result, output


class TestTwoSum:
    """End-to-end test for arrays/two_sum."""

    def test_sample_solution_passes_all(self):
        result, output = _run_problem_e2e("arrays/two_sum")
        assert result.score == 1.0, (
            f"Expected perfect score, got {result.score}. "
            f"Failed: {[c.name for c in result.checks if not c.passed]}"
        )
        assert "Grade" in output
        assert "✓" in output


class TestReverseWords:
    """End-to-end test for strings/reverse_words."""

    def test_sample_solution_passes_all(self):
        result, output = _run_problem_e2e("strings/reverse_words")
        assert result.score == 1.0, (
            f"Expected perfect score, got {result.score}. "
            f"Failed: {[c.name for c in result.checks if not c.passed]}"
        )


class TestReverseList:
    """End-to-end test for linked_lists/reverse_list."""

    def test_sample_solution_passes_all(self):
        result, output = _run_problem_e2e("linked_lists/reverse_list")
        assert result.score == 1.0, (
            f"Expected perfect score, got {result.score}. "
            f"Failed: {[c.name for c in result.checks if not c.passed]}"
        )


class TestInorderTraversal:
    """End-to-end test for trees/inorder_traversal."""

    def test_sample_solution_passes_all(self):
        result, output = _run_problem_e2e("trees/inorder_traversal")
        assert result.score == 1.0, (
            f"Expected perfect score, got {result.score}. "
            f"Failed: {[c.name for c in result.checks if not c.passed]}"
        )


class TestMergeSort:
    """End-to-end test for sorting/merge_sort."""

    def test_sample_solution_passes_all(self):
        result, output = _run_problem_e2e("sorting/merge_sort")
        assert result.score == 1.0, (
            f"Expected perfect score, got {result.score}. "
            f"Failed: {[c.name for c in result.checks if not c.passed]}"
        )


class TestRendering:
    """Test that rendering works for various scenarios."""

    def test_practice_mode_output(self):
        result, output = _run_problem_e2e("arrays/two_sum")
        assert "Score:" in output
        assert "✓" in output

    def test_output_contains_problem_name(self):
        result, output = _run_problem_e2e("arrays/two_sum")
        assert "Two Sum" in output

    def test_perfect_score_encouragement(self):
        result, output = _run_problem_e2e("arrays/two_sum")
        assert "Accepted. All tests passed." in output


class TestSuiteResult:
    """Test SuiteResult serialization."""

    def test_to_json(self):
        result, _ = _run_problem_e2e("arrays/two_sum")
        json_str = result.to_json()
        import json
        data = json.loads(json_str)
        assert data["problem"] == "Two Sum"
        assert data["score"] == 1.0
        assert len(data["checks"]) >= 4

    def test_to_file(self, tmp_path):
        result, _ = _run_problem_e2e("arrays/two_sum")
        out_file = tmp_path / "results.json"
        result.to_file(out_file)
        assert out_file.exists()
        import json
        data = json.loads(out_file.read_text())
        assert data["problem"] == "Two Sum"
