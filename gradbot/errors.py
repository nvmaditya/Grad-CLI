# SPDX-License-Identifier: GPL-3.0-only
"""Errors whose message is written for the person running the command."""

from __future__ import annotations


class UserError(Exception):
    """The CLI prints the message and exits 1. No traceback, no "bug in GradBot"."""
