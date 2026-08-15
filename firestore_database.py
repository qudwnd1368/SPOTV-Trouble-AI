"""Firestore implementation used by the Cloud Run deployment."""

import os
from datetime import datetime, timezone

from models import Incident
from seed_data import SEED_INCIDENTS

COLLECTION = os.getenv("FIRESTORE_COLLECTION", "incidents")


def _client():
    try:
        from google.cloud import firestore
    except ImportError as exc:
        raise RuntimeError("Firestore support is not installed. Run pip install -r requirements.txt.") from exc
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or None
    return firestore.Client(project=project)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _collection():
    return _client().collection(COLLECTION)


def _to_incident(snapshot):
    data = snapshot.to_dict() or {}
    return Incident(
        id=snapshot.id,
        incident_number=str(data.get("incident_number", "")),
        occurred_at=data.get("occurred_at"),
        equipment=data.get("equipment", ""),
        symptom=data.get("symptom", ""),
        cause=data.get("cause", ""),
        action=data.get("action", ""),
        notes=data.get("notes", ""),
        created_at=data.get("created_at"),
        updated_at=data.get("updated_at"),
        embedding=data.get("embedding"),
    )


def _clean(data, embedding=None, created_at=None):
    now = _now()
    return {
        "incident_number": data["incident_number"].strip(),
        "occurred_at": data.get("occurred_at") or None,
        "equipment": data["equipment"].strip(),
        "symptom": data["symptom"].strip(),
        "cause": data["cause"].strip(),
        "action": data["action"].strip(),
        "notes": data.get("notes", "").strip(),
        "embedding": embedding,
        "created_at": created_at or now,
        "updated_at": now,
    }


def _find_by_number(incident_number):
    query = _collection().where("incident_number", "==", incident_number).limit(1)
    return next(iter(query.stream()), None)


def init_db():
    collection = _collection()
    if next(iter(collection.limit(1).stream()), None) is None:
        for item in SEED_INCIDENTS:
            collection.document().set(_clean(item))


def list_incidents():
    snapshots = _collection().order_by("incident_number").stream()
    return [_to_incident(snapshot) for snapshot in snapshots]


def add_incident(data, embedding=None):
    if _find_by_number(data["incident_number"].strip()):
        raise ValueError("이미 사용 중인 사고번호입니다.")
    _collection().document().set(_clean(data, embedding))


def update_incident(incident_id, data, embedding=None):
    duplicate = _find_by_number(data["incident_number"].strip())
    if duplicate and duplicate.id != str(incident_id):
        raise ValueError("이미 사용 중인 사고번호입니다.")
    reference = _collection().document(str(incident_id))
    current = reference.get()
    created_at = (current.to_dict() or {}).get("created_at") if current.exists else None
    reference.set(_clean(data, embedding, created_at))


def delete_incident(incident_id):
    _collection().document(str(incident_id)).delete()


def stats():
    items = list_incidents()
    return len(items), len({item.equipment for item in items}), max((item.updated_at or "" for item in items), default="-")


def upsert_by_incident_number(data, embedding=None):
    existing = _find_by_number(data["incident_number"].strip())
    if existing:
        update_incident(existing.id, data, embedding)
    else:
        add_incident(data, embedding)
