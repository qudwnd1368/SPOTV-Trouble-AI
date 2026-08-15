"""Storage facade: SQLite locally, Firestore in Google Cloud."""

import os


def _backend():
    if os.getenv("DATABASE_BACKEND", "sqlite").strip().lower() == "firestore":
        import firestore_database
        return firestore_database
    import database
    return database


def init_db(*args, **kwargs):
    return _backend().init_db(*args, **kwargs)


def list_incidents(*args, **kwargs):
    return _backend().list_incidents(*args, **kwargs)


def add_incident(*args, **kwargs):
    return _backend().add_incident(*args, **kwargs)


def update_incident(*args, **kwargs):
    return _backend().update_incident(*args, **kwargs)


def delete_incident(*args, **kwargs):
    return _backend().delete_incident(*args, **kwargs)


def stats(*args, **kwargs):
    return _backend().stats(*args, **kwargs)
