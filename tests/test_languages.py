"""Every supported language, compiled and run for real. Skipped when the toolchain is missing."""

from __future__ import annotations

from pathlib import Path

import pytest

from gradbot.cli import grade_dev
from tests.samples_repo import TWO_SUM_CHECKS, TWO_SUM_SOLUTION, TWO_SUM_SUITE
from tests.toolchains import needs_gcc, needs_gxx, needs_jdk

C_TWO_SUM = """\
#include <stdio.h>
int main(void) {
    int n, target;
    static int a[100000];
    if (scanf("%d", &n) != 1 || n > 100000) return 1;
    for (int i = 0; i < n; i++) scanf("%d", &a[i]);
    scanf("%d", &target);
    for (int i = 0; i < n; i++)
        for (int j = i + 1; j < n; j++)
            if (a[i] + a[j] == target) { printf("%d %d\\n", i, j); return 0; }
    return 0;
}
"""

CPP_TWO_SUM = """\
#include <iostream>
#include <unordered_map>
#include <vector>
int main() {
    int n; std::cin >> n;
    std::vector<long long> a(n);
    for (auto &x : a) std::cin >> x;
    long long target; std::cin >> target;
    std::unordered_map<long long, int> seen;
    for (int i = 0; i < n; i++) {
        auto it = seen.find(target - a[i]);
        if (it != seen.end()) { std::cout << it->second << " " << i << "\\n"; return 0; }
        seen[a[i]] = i;
    }
}
"""

JAVA_TWO_SUM = """\
import java.util.*;

public class Solution {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in);
        int n = in.nextInt();
        long[] a = new long[n];
        for (int i = 0; i < n; i++) a[i] = in.nextLong();
        long target = in.nextLong();
        Map<Long, Integer> seen = new HashMap<>();
        for (int i = 0; i < n; i++) {
            Integer j = seen.get(target - a[i]);
            if (j != null) { System.out.println(j + " " + i); return; }
            seen.put(a[i], i);
        }
    }
}
"""

CASES = [
    pytest.param("solution.py", TWO_SUM_SOLUTION, "print(1 1)\n", id="python"),
    pytest.param("solution.c", C_TWO_SUM, "int main(void) {\n  return 0\n}\n", id="c", marks=needs_gcc),
    pytest.param("solution.cpp", CPP_TWO_SUM, "int main() {\n  int x = ;\n}\n", id="cpp", marks=needs_gxx),
    pytest.param(
        "Solution.java", JAVA_TWO_SUM,
        "public class Solution {\n  public static void main(String[] a) {\n    int x = \n  }\n}\n",
        id="java", marks=needs_jdk,
    ),
]


def _grade(tmp_path: Path, filename: str, source: str, capsys) -> tuple[int, str]:
    suite = tmp_path / "suite"
    suite.mkdir(exist_ok=True)
    (suite / "suite.yaml").write_text(TWO_SUM_SUITE, encoding="utf-8")
    (suite / "checks.py").write_text(TWO_SUM_CHECKS, encoding="utf-8")
    sol = tmp_path / "sol"
    sol.mkdir(exist_ok=True)
    (sol / filename).write_text(source, encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        grade_dev(suite, sol, no_color=True)
    return exc.value.code, capsys.readouterr().out


@pytest.mark.parametrize(("filename", "good", "broken"), CASES)
def test_correct_solution_passes(tmp_path, capsys, filename, good, broken):
    code, out = _grade(tmp_path, filename, good, capsys)
    assert code == 0, out
    assert "Score: 1 / 1" in out


@pytest.mark.parametrize(("filename", "good", "broken"), CASES)
def test_compile_error_names_the_line_and_skips_checks(tmp_path, capsys, filename, good, broken):
    code, out = _grade(tmp_path, filename, broken, capsys)
    assert code == 1
    assert "error on line" in out, out
    assert "skipped" in out
    assert "Score: 0 / 1" in out


@pytest.mark.parametrize(("filename", "good", "broken"), CASES)
def test_wrong_answer_fails_with_the_check_hint(tmp_path, capsys, filename, good, broken):
    wrong = good.replace("i, j", "j, i").replace("seen[target - num], i", "i, seen[target - num]")
    wrong = wrong.replace('it->second << " " << i', 'i << " " << it->second')
    wrong = wrong.replace('j + " " + i', 'i + " " + j')
    code, out = _grade(tmp_path, filename, wrong, capsys)
    assert code == 1, out
    assert "Use a hash map" in out


_BUNDLED_TWO_SUM = Path(__file__).resolve().parent.parent / "problems" / "arrays" / "two_sum"


@pytest.mark.parametrize(("filename", "good", "broken"), CASES)
def test_correct_solution_passes_the_bundled_problem_with_its_large_input(
    tmp_path, capsys, filename, good, broken,
):
    # The bundled checks send 10,000 numbers; the small suite above sends four.
    sol = tmp_path / "sol"
    sol.mkdir()
    (sol / filename).write_text(good, encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        grade_dev(_BUNDLED_TWO_SUM, sol, no_color=True)
    out = capsys.readouterr().out
    assert exc.value.code == 0, out
    assert "Score: 4 / 4" in out
