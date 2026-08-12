"""Firestore implementation used by the Cloud Run deployment."""

import os
import time
from datetime import datetime, timezone

from models import Incident
from seed_data import SEED_INCIDENTS

COLLECTION = os.getenv("FIRESTORE_COLLECTION", "incidents")
MANUAL_COLLECTION = os.getenv("FIRESTORE_MANUAL_COLLECTION", "manuals")
MANUAL_INDEX_COLLECTION = os.getenv("FIRESTORE_MANUAL_INDEX_COLLECTION", "manual_index_parts")
_MANUAL_CACHE = {"loaded_at": 0.0, "chunks": None}


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


def _manual_collection():
    return _client().collection(MANUAL_COLLECTION)


def _manual_index_collection():
    return _client().collection(MANUAL_INDEX_COLLECTION)


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


def list_manuals():
    return [snapshot.to_dict() or {} for snapshot in _manual_collection().order_by("title").stream()]


def list_manual_chunks():
    if _MANUAL_CACHE["chunks"] is not None and time.monotonic() - _MANUAL_CACHE["loaded_at"] < 300:
        return _MANUAL_CACHE["chunks"]
    chunks = []
    for snapshot in _manual_index_collection().stream():
        chunks.extend((snapshot.to_dict() or {}).get("chunks", []))
    _MANUAL_CACHE.update({"loaded_at": time.monotonic(), "chunks": chunks})
    return chunks


def _delete_query(query):
    pending = []
    for snapshot in query.stream():
        pending.append(snapshot.reference)
        if len(pending) == 400:
            batch = _client().batch()
            for reference in pending:
                batch.delete(reference)
            batch.commit()
            pending = []
    if pending:
        batch = _client().batch()
        for reference in pending:
            batch.delete(reference)
        batch.commit()


def _pack_chunks(chunks, max_chars=500_000):
    parts, current, current_size = [], [], 0
    for chunk in chunks:
        size = len(chunk.get("content", "")) + len(chunk.get("title", "")) + 200
        if current and current_size + size > max_chars:
            parts.append(current)
            current, current_size = [], 0
        current.append(chunk)
        current_size += size
    if current:
        parts.append(current)
    return parts


def replace_manual(metadata, chunks):
    manual_id = str(metadata["id"])
    _delete_query(_manual_index_collection().where("manual_id", "==", manual_id))
    batch = _client().batch()
    for index, part in enumerate(_pack_chunks(chunks)):
        reference = _manual_index_collection().document(f"{manual_id}-{index:04d}")
        batch.set(reference, {"manual_id": manual_id, "part": index, "chunks": part})
    batch.set(_manual_collection().document(manual_id), metadata)
    batch.commit()
    _MANUAL_CACHE.update({"loaded_at": 0.0, "chunks": None})


def delete_manual(manual_id):
    manual_id = str(manual_id)
    _delete_query(_manual_index_collection().where("manual_id", "==", manual_id))
    _manual_collection().document(manual_id).delete()
    _MANUAL_CACHE.update({"loaded_at": 0.0, "chunks": None})


def manual_stats():
    manuals = list_manuals()
    return len(manuals), sum(item.get("page_count", 0) for item in manuals), sum(item.get("chunk_count", 0) for item in manuals)
