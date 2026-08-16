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


def list_knowledge_items(*args, **kwargs):
    return _backend().list_knowledge_items(*args, **kwargs)


def add_knowledge_item(*args, **kwargs):
    return _backend().add_knowledge_item(*args, **kwargs)


def update_knowledge_item(*args, **kwargs):
    return _backend().update_knowledge_item(*args, **kwargs)


def delete_knowledge_item(*args, **kwargs):
    return _backend().delete_knowledge_item(*args, **kwargs)


def stats(*args, **kwargs):
    return _backend().stats(*args, **kwargs)


list_incidents = list_knowledge_items
add_incident = add_knowledge_item
update_incident = update_knowledge_item
delete_incident = delete_knowledge_item
