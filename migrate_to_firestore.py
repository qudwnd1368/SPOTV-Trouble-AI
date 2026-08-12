"""Copy the local SQLite incidents into the configured Firestore project."""

import os

from dotenv import load_dotenv

import database
import firestore_database


def main():
    load_dotenv()
    if not os.getenv("GOOGLE_CLOUD_PROJECT"):
        raise SystemExit("GOOGLE_CLOUD_PROJECT is required.")
    database.init_db()
    incidents = database.list_incidents()
    for item in incidents:
        firestore_database.upsert_by_incident_number({
            "incident_number": item.incident_number,
            "occurred_at": item.occurred_at,
            "equipment": item.equipment,
            "symptom": item.symptom,
            "cause": item.cause,
            "action": item.action,
            "notes": item.notes,
        }, item.embedding)
    print(f"Migrated {len(incidents)} incidents to Firestore.")


if __name__ == "__main__":
    main()

