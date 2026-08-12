import os

import storage


def test_storage_defaults_to_sqlite(monkeypatch):
    monkeypatch.delenv("DATABASE_BACKEND", raising=False)
    assert storage._backend().__name__ == "database"


def test_storage_selects_firestore_without_connecting(monkeypatch):
    monkeypatch.setenv("DATABASE_BACKEND", "firestore")
    assert storage._backend().__name__ == "firestore_database"

