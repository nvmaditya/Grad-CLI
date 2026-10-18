"""The course grade workflow stays off GitHub Pages and clears the faculty token."""

from gradbot.grade_workflow import grade_workflow_text


def test_workflow_grades_in_the_course_repo_and_hides_the_token():
    text = grade_workflow_text()
    assert "pages" not in text.lower()
    assert "github.io" not in text
    assert text.count("${{ secrets.GRADE_APP_TOKEN }}") == 1

    student = text.split("- name: Check out the student commit", 1)[1]
    student = student.split("- name: Grade", 1)[0]
    assert "${{ secrets.GRADE_APP_TOKEN }}" in student

    grade = text.split("- name: Grade", 1)[1]
    assert 'GRADE_APP_TOKEN: ""' in grade
    assert 'GITHUB_TOKEN: ""' in grade
    assert 'GRADBOT_APP_TOKEN: ""' in grade
    assert grade.index('GRADE_APP_TOKEN: ""') < grade.index("python -m gradbot dev")
    assert "checks_hidden.py" not in grade.split("python -m gradbot dev", 1)[1]
