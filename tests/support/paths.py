"""Resolve project paths independently of test directory depth."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
