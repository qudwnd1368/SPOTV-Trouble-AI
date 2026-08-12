import database as db
from search import manual_search, semantic_search


def seeded(tmp_path):
    path = tmp_path / "test.db"
    db.init_db(path)
    return db.list_incidents(path), path


def test_required_queries(tmp_path):
    incidents, _ = seeded(tmp_path)
    cases = {
        "EVS 입력 안 들어와": "001",
        "스트림덱 빨간불 들어오고 버튼이 안 먹어": "002",
        "CL3 페이더 내렸는데 소리가 계속 나가": "005",
        "다음 VCR이 첫 화면에서 멈춰": "004",
    }
    for query, expected in cases.items():
        top_three = [item.incident_number for _, item in semantic_search(query, incidents)]
        assert expected in top_three, (query, top_three)


def test_nullable_date_and_crud(tmp_path):
    incidents, path = seeded(tmp_path)
    assert len(incidents) == 5 and all(i.occurred_at is None for i in incidents)
    data = {"incident_number":"006", "occurred_at":None, "equipment":"TEST", "symptom":"신호 없음", "cause":"케이블", "action":"교체", "notes":""}
    db.add_incident(data, "[1, 0]", path)
    item = db.list_incidents(path)[-1]
    data["symptom"] = "영상 신호 없음"
    db.update_incident(item.id, data, "[0, 1]", path)
    assert db.list_incidents(path)[-1].embedding == "[0, 1]"
    db.delete_incident(item.id, path)
    assert len(db.list_incidents(path)) == 5


def test_manual_storage_and_search(tmp_path):
    path = tmp_path / "manual.db"
    db.init_db(path)
    metadata = {
        "id": "xtnano", "title": "EVS XTnano 테크니컬 매뉴얼.pdf",
        "drive_file_id": "drive-1", "drive_url": "https://example.test/manual",
        "file_hash": "abc", "page_count": 2, "extracted_pages": 2,
        "chunk_count": 2, "updated_at": "2026-08-12T00:00:00+00:00",
    }
    chunks = [
        {"id": "c1", "manual_id": "xtnano", "title": metadata["title"], "page_number": 10,
         "content": "RAID disk failure LED가 켜진 경우 디스크 상태를 확인한다.", "drive_url": metadata["drive_url"]},
        {"id": "c2", "manual_id": "xtnano", "title": metadata["title"], "page_number": 20,
         "content": "전원 공급 장치와 팬 교체 절차", "drive_url": metadata["drive_url"]},
    ]
    db.replace_manual(metadata, chunks, path)
    assert db.manual_stats(path) == (1, 2, 2)
    results = manual_search("XTnano RAID disk failure", db.list_manual_chunks(path))
    assert results[0][1]["page_number"] == 10
    db.delete_manual("xtnano", path)
    assert db.manual_stats(path) == (0, 0, 0)
