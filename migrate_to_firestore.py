"""Copy the local SQLite knowledge items into the configured Firestore project."""

import os

from dotenv import load_dotenv

import database
import firestore_database


def main():
    load_dotenv()
    if not os.getenv("GOOGLE_CLOUD_PROJECT"):
        raise SystemExit("GOOGLE_CLOUD_PROJECT is required.")
    database.init_db()
    items = database.list_knowledge_items()
    for item in items:
        firestore_database.upsert_by_title({
            "title": item.title,
            "context": item.context,
            "action": item.action,
            "caution": item.caution,
        }, item.embedding)
    print(f"Migrated {len(items)} knowledge items to Firestore.")


if __name__ == "__main__":
    main()
