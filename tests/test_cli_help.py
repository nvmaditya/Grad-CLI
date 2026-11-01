"""Every command, subcommand and argument explains itself in --help."""

from __future__ import annotations

import argparse

import pytest

from gradbot.cli import _HANDLERS, main


@pytest.fixture
def undocumented(monkeypatch) -> list[str]:
    """Records every parser, subcommand and argument declared without help text."""
    missing: list[str] = []
    real_init = argparse.ArgumentParser.__init__
    real_add_argument = argparse._ActionsContainer.add_argument
    real_add_parser = argparse._SubParsersAction.add_parser

    def init(self, *args, **kwargs):
        real_init(self, *args, **kwargs)
        if not self.description:
            missing.append(f"{self.prog}: no description")

    def add_argument(self, *args, **kwargs):
        action = real_add_argument(self, *args, **kwargs)
        if not action.help:
            missing.append(f"{'/'.join(action.option_strings) or action.dest}: no help")
        return action

    def add_parser(self, name, **kwargs):
        if not kwargs.get("help"):
            missing.append(f"subcommand {name}: no help")
        return real_add_parser(self, name, **kwargs)

    monkeypatch.setattr(argparse.ArgumentParser, "__init__", init)
    monkeypatch.setattr(argparse._ActionsContainer, "add_argument", add_argument)
    monkeypatch.setattr(argparse._SubParsersAction, "add_parser", add_parser)
    return missing


@pytest.mark.parametrize("command", [*_HANDLERS, "(legacy)"])
def test_every_command_documents_its_arguments(command, undocumented, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"] if command == "(legacy)" else [command, "--help"])
    assert exc.value.code == 0
    assert "usage:" in capsys.readouterr().out
    assert undocumented == []
