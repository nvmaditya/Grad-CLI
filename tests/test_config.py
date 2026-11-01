"""gradbot.config reads the environment at call time; .env.example documents every variable."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from gradbot.config import VARIABLES, ConfigError, load, require, require_owner_repo

ROOT = Path(__file__).resolve().parent.parent


def test_defaults_without_any_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    settings = load({})
    assert settings.public_repo == "nvmaditya/gradbot-course-samples"
    assert settings.github_url == "https://github.com"
    assert settings.github_api_url == "https://api.github.com"
    assert settings.client_id is None
    assert settings.token_file.name == "github_token"


def test_values_are_read_at_call_time(monkeypatch):
    monkeypatch.setenv("GRADBOT_PUBLIC_REPO", "acme/one")
    first = load().public_repo
    monkeypatch.setenv("GRADBOT_PUBLIC_REPO", "acme/two")
    assert (first, load().public_repo) == ("acme/one", "acme/two")


def test_blank_values_count_as_unset():
    settings = load({"GRADBOT_CLIENT_ID": "   ", "GRADBOT_PUBLIC_REPO": ""})
    assert settings.client_id is None
    assert settings.public_repo == "nvmaditya/gradbot-course-samples"


def test_enterprise_urls_lose_a_trailing_slash():
    settings = load({"GRADBOT_GITHUB_API_URL": "https://ghe.example.com/api/v3/"})
    assert settings.github_api_url == "https://ghe.example.com/api/v3"


def test_require_names_the_variable_and_the_reason():
    with pytest.raises(ConfigError, match="GRADBOT_CLIENT_ID is not set. Ask your teacher"):
        require(None, "GRADBOT_CLIENT_ID", "Ask your teacher.")
    assert require("x", "GRADBOT_CLIENT_ID", "") == "x"


@pytest.mark.parametrize("value", ["acme", "acme/b/c", "acme/../x", "https://github.com/acme/x"])
def test_require_owner_repo_refuses_other_shapes(value):
    with pytest.raises(ConfigError, match="owner/repo"):
        require_owner_repo(value, "GRADBOT_SUBMISSIONS_REPO", "")


def test_env_example_documents_every_variable():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    documented = set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", text, flags=re.MULTILINE))
    assert {v.name for v in VARIABLES} <= documented
    for variable in VARIABLES:
        label = "REQUIRED" if variable.required else "OPTIONAL"
        block = text.split(f"{variable.name}=")[0].rsplit("\n\n", 1)[-1]
        assert label in block, f"{variable.name} should be marked {label} in .env.example"


def test_every_variable_read_by_the_code_is_declared():
    source = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "gradbot").glob("*.py"))
    read = set(re.findall(r'"((?:GRADBOT|GRADE)_[A-Z_]+)"', source)) | {"NO_COLOR"}
    # Names that appear only inside the grader workflow templates or as secret-name parts.
    workflow_only = {"GRADE_APP_TOKEN", "GRADBOT_PIP_SPEC"}
    assert read - workflow_only <= {v.name for v in VARIABLES}
