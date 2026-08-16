import sqlite3
import uuid
from pathlib import Path

from models import KnowledgeItem
from seed_data import SEED_KNOWLEDGE_ITEMS

DB_PATH = Path(__file__).with_name("spotv_trouble.db")


def connect(db_path=DB_PATH):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path=DB_PATH):
    with connect(db_path) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_number TEXT NOT NULL UNIQUE,
            occurred_at TEXT NULL,
            equipment TEXT NOT NULL DEFAULT '',
            symptom TEXT NOT NULL DEFAULT '',
            cause TEXT NOT NULL DEFAULT '',
            action TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            context TEXT NOT NULL DEFAULT '',
            caution TEXT NOT NULL DEFAULT '',
            embedding TEXT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        _ensure_column(con, "title", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(con, "context", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(con, "caution", "TEXT NOT NULL DEFAULT ''")
        _backfill_knowledge_fields(con)
        if con.execute("SELECT COUNT(*) FROM incidents").fetchone()[0] == 0:
            for item in SEED_KNOWLEDGE_ITEMS:
                _insert(con, item)


def _ensure_column(con, name, definition):
    columns = {row["name"] for row in con.execute("PRAGMA table_info(incidents)")}
    if name not in columns:
        con.execute(f"ALTER TABLE incidents ADD COLUMN {name} {definition}")


def _backfill_knowledge_fields(con):
    rows = con.execute("SELECT * FROM incidents WHERE title='' OR context='' OR caution=''").fetchall()
    for row in rows:
        data = dict(row)
        item = _normalize_data(data)
        con.execute("""UPDATE incidents SET title=?, context=?, caution=? WHERE id=?""", (
            item["title"], item["context"], item["caution"], data["id"],
        ))


def _normalize_data(data):
    title = (data.get("title") or "").strip()
    context = (data.get("context") or "").strip()
    action = (data.get("action") or "").strip()
    caution = (data.get("caution") or "").strip()

    legacy_equipment = (data.get("equipment") or "").strip()
    legacy_symptom = (data.get("symptom") or "").strip()
    legacy_cause = (data.get("cause") or "").strip()
    legacy_notes = (data.get("notes") or "").strip()

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
        "incident_number": (data.get("incident_number") or uuid.uuid4().hex[:12]).strip(),
        "occurred_at": data.get("occurred_at") or None,
        "equipment": legacy_equipment or title,
        "symptom": legacy_symptom or context,
        "cause": legacy_cause,
        "notes": legacy_notes or caution,
    }


def _insert(con, data, embedding=None):
    item = _normalize_data(data)
    con.execute("""INSERT INTO incidents
        (incident_number, occurred_at, equipment, symptom, cause, action, notes, title, context, caution, embedding)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
        item["incident_number"], item["occurred_at"], item["equipment"], item["symptom"],
        item["cause"], item["action"], item["notes"], item["title"], item["context"],
        item["caution"], embedding,
    ))


def _row_to_knowledge(row):
    data = _normalize_data(dict(row))
    return KnowledgeItem(
        id=row["id"],
        title=data["title"],
        context=data["context"],
        action=data["action"],
        caution=data["caution"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        embedding=row["embedding"],
    )


def list_knowledge_items(db_path=DB_PATH):
    with connect(db_path) as con:
        return [_row_to_knowledge(row) for row in con.execute("SELECT * FROM incidents ORDER BY updated_at DESC, id DESC")]


def add_knowledge_item(data, embedding=None, db_path=DB_PATH):
    with connect(db_path) as con:
        _insert(con, data, embedding)


def update_knowledge_item(item_id: int, data, embedding=None, db_path=DB_PATH):
    item = _normalize_data(data)
    with connect(db_path) as con:
        current = con.execute("SELECT incident_number, occurred_at, equipment, symptom, cause, notes FROM incidents WHERE id=?", (item_id,)).fetchone()
        if current:
            existing = _normalize_data({**dict(current), **data})
            item["incident_number"] = existing["incident_number"]
            item["occurred_at"] = existing["occurred_at"]
        con.execute("""UPDATE incidents SET equipment=?, symptom=?, cause=?, action=?, notes=?,
            title=?, context=?, caution=?, embedding=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""", (
            item["equipment"], item["symptom"], item["cause"], item["action"], item["notes"],
            item["title"], item["context"], item["caution"], embedding, item_id,
        ))


def delete_knowledge_item(item_id: int, db_path=DB_PATH):
    with connect(db_path) as con:
        con.execute("DELETE FROM incidents WHERE id=?", (item_id,))


def stats(db_path=DB_PATH):
    items = list_knowledge_items(db_path)
    return len(items), 0, max((item.updated_at or "" for item in items), default="-")


list_incidents = list_knowledge_items
add_incident = add_knowledge_item
update_incident = update_knowledge_item
delete_incident = delete_knowledge_item
