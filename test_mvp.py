import database as db
from search import semantic_search


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
