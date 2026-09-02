"""Env must be set before app.config / app.db bind the engine."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_DB = Path(__file__).resolve().parent / "_pytest.sqlite"
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB}"
os.environ["ALLOW_ORIGINS"] = "http://localhost:3000,http://127.0.0.1:3000"

if _DB.exists():
    _DB.unlink()
for leftover in _DB.parent.glob("_pytest.sqlite*"):
    leftover.unlink()


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def test_db_path() -> Path:
    return _DB
