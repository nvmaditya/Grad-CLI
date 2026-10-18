"""Grade CLI — free course grading on a free GitHub organization."""

from setuptools import setup, find_packages
from pathlib import Path

try:
    long_description = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")
except FileNotFoundError:
    long_description = "Grade CLI — free course grading on a free GitHub organization"

setup(
    name="grade-cli",
    version="1.0.0",
    description="Free course grading on a free GitHub organization",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="GradBot Team",
    license="GPL-3.0-only",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "pyyaml>=6.0",
    ],
    extras_require={
        "rich": ["rich>=13.0"],
        "dev": [
            "pytest>=7.0",
            "pytest-mock>=3.10",
            "responses>=0.23",
        ],
    },
    entry_points={
        "console_scripts": [
            "grade = gradbot.cli:main",
            "GradBot = gradbot.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Education",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Education",
    ],
)
