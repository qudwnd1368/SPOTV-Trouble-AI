"""Firestore implementation used by the Cloud Run deployment."""

import os
import uuid
from datetime import datetime, timezone

from models import KnowledgeItem
from seed_data import SEED_KNOWLEDGE_ITEMS

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


def _normalize_data(data):
    title = str(data.get("title") or "").strip()
    context = str(data.get("context") or "").strip()
    action = str(data.get("action") or "").strip()
    caution = str(data.get("caution") or "").strip()

    legacy_equipment = str(data.get("equipment") or "").strip()
    legacy_symptom = str(data.get("symptom") or "").strip()
    legacy_cause = str(data.get("cause") or "").strip()
    legacy_notes = str(data.get("notes") or "").strip()
    images = data.get("images") or []
    images = [image for image in images if isinstance(image, dict)] if isinstance(images, list) else []

    if not title:
        title = " ".join(part for part in [legacy_equipment, legacy_symptom] if part).strip()
    if not context:
        context = legacy_symptom
    if not caution:
        caution = "\n".join(part for part in [legacy_cause, legacy_notes] if part).strip()

    return {
        "title": title,
        "context": context,
        "action": action,
        "caution": caution,
        "incident_number": str(data.get("incident_number") or uuid.uuid4().hex[:12]).strip(),
        "occurred_at": data.get("occurred_at"),
        "equipment": legacy_equipment or title,
        "symptom": legacy_symptom or context,
        "cause": legacy_cause,
        "notes": legacy_notes or caution,
        "images": images,
    }


def _to_knowledge(snapshot):
    raw = snapshot.to_dict() or {}
    data = _normalize_data(raw)
    return KnowledgeItem(
        id=snapshot.id,
        title=data["title"],
        context=data["context"],
        action=data["action"],
        caution=data["caution"],
        created_at=raw.get("created_at"),
        updated_at=raw.get("updated_at"),
        embedding=raw.get("embedding"),
        images=data["images"],
    )


def _clean(data, embedding=None, created_at=None):
    now = _now()
    item = _normalize_data(data)
    return {
        **item,
        "embedding": embedding,
        "created_at": created_at or now,
        "updated_at": now,
    }


def init_db():
    collection = _collection()
    if next(iter(collection.limit(1).stream()), None) is None:
        for item in SEED_KNOWLEDGE_ITEMS:
            collection.document().set(_clean(item))


def list_knowledge_items():
    snapshots = _collection().stream()
    items = [_to_knowledge(snapshot) for snapshot in snapshots]
    return sorted(items, key=lambda item: item.updated_at or "", reverse=True)


def add_knowledge_item(data, embedding=None):
    reference = _collection().document()
    reference.set(_clean(data, embedding))
    return reference.id


def update_knowledge_item(item_id, data, embedding=None):
    reference = _collection().document(str(item_id))
    current = reference.get()
    raw = current.to_dict() or {}
    created_at = raw.get("created_at") if current.exists else None
    incoming = dict(data)
    if "caution" in incoming:
        incoming["cause"] = ""
        incoming["notes"] = incoming["caution"]
    reference.set(_clean({**raw, **incoming}, embedding, created_at))


def delete_knowledge_item(item_id):
    _collection().document(str(item_id)).delete()


def stats():
    items = list_knowledge_items()
    return len(items), 0, max((item.updated_at or "" for item in items), default="-")


def upsert_by_title(data, embedding=None):
    title = _normalize_data(data)["title"]
    query = _collection().where("title", "==", title).limit(1)
    existing = next(iter(query.stream()), None)
    if existing:
        update_knowledge_item(existing.id, data, embedding)
    else:
        add_knowledge_item(data, embedding)


def upsert_by_incident_number(data, embedding=None):
    incident_number = _normalize_data(data)["incident_number"]
    query = _collection().where("incident_number", "==", incident_number).limit(1)
    existing = next(iter(query.stream()), None)
    if existing:
        update_knowledge_item(existing.id, data, embedding)
    else:
        add_knowledge_item(data, embedding)


list_incidents = list_knowledge_items
add_incident = add_knowledge_item
update_incident = update_knowledge_item
delete_incident = delete_knowledge_item
