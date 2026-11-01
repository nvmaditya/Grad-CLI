# GradBot — course grade workflow for a free GitHub organization.
# Copyright (C) 2026 Aditya Khandelwal
# SPDX-License-Identifier: GPL-3.0-only

"""Workflow text for a grade that runs in the course repository."""

from __future__ import annotations

from gradbot.policy import INSTALL_SPEC


def grade_workflow_text() -> str:
    return _TEXT.replace("@INSTALL_SPEC@", INSTALL_SPEC)


_TEXT = """\
name: grade

on:
  workflow_dispatch:
    inputs:
      slug:
        required: true
        type: string
      user_id:
        required: true
        type: string
      repository:
        required: true
        type: string
      sha:
        required: true
        type: string

permissions:
  contents: read

concurrency:
  group: grade-${{ inputs.user_id }}-${{ inputs.slug }}
  cancel-in-progress: false

jobs:
  grade:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - name: Check out the course
        uses: actions/checkout@v7
        with:
          path: course
          persist-credentials: false

      - name: Check out the student commit
        uses: actions/checkout@v7
        with:
          repository: ${{ inputs.repository }}
          ref: ${{ inputs.sha }}
          token: ${{ secrets.GRADE_APP_TOKEN }}
          path: submission
          persist-credentials: false

      - name: Set up Python
        uses: actions/setup-python@v7
        with:
          python-version: "3.12"

      - name: Install GradBot
        env:
          GRADBOT_PIP_SPEC: ${{ vars.GRADBOT_PIP_SPEC || '@INSTALL_SPEC@' }}
        run: python -m pip install "$GRADBOT_PIP_SPEC"

      - name: Grade
        continue-on-error: true
        env:
          GRADE_APP_TOKEN: ""
          GITHUB_TOKEN: ""
          GRADBOT_APP_TOKEN: ""
          SLUG: ${{ inputs.slug }}
        run: |
          case "$SLUG" in *..*) echo "refusing a path with .."; exit 1;; esac
          python -m gradbot dev "course/$SLUG" --solution submission --sandbox docker --output faculty.json --student-output student.json

      - name: Check that grading finished
        # The Grade step may fail because the student's program did; that is
        # a finished grade. A missing student.json means the grader itself broke.
        run: test -f student.json || { echo "::error::grading did not finish; see the Grade step"; exit 1; }
"""
