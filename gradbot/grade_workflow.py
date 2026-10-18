# Grade CLI — course grade workflow for a free GitHub organization.
# Copyright (C) 2026 Grade CLI contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Workflow text for a grade that runs in the course repository."""

from __future__ import annotations


def grade_workflow_text() -> str:
    return """\
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
        uses: actions/checkout@v4
        with:
          path: course

      - name: Check out the student commit
        uses: actions/checkout@v4
        with:
          repository: ${{ inputs.repository }}
          ref: ${{ inputs.sha }}
          token: ${{ secrets.GRADE_APP_TOKEN }}
          path: submission

      - name: Grade
        env:
          GRADE_APP_TOKEN: ""
          GITHUB_TOKEN: ""
          GRADBOT_APP_TOKEN: ""
        run: python -m gradbot dev "course/${{ inputs.slug }}" --solution submission --sandbox docker --output faculty.json --student-output student.json
"""
