"""GradBot — CLI grading tool for cohort DSA and competitive programming."""

from setuptools import setup, find_packages
from pathlib import Path

try:
    long_description = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")
except FileNotFoundError:
    long_description = "GradBot — A CLI grading tool for cohort DSA and competitive programming"

setup(
    name="gradbot",
    version="1.0.0",
    description="A CLI grading tool for coding-cohort students, mainly DSA and competitive programming",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="GradBot Team",
    license="MIT",
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
            "GradBot = gradbot.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Education",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Education",
    ],
)
