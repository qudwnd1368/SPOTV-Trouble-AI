import database as db
from search import semantic_search


def seeded(tmp_path):
    path = tmp_path / "test.db"
    db.init_db(path)
    return db.list_knowledge_items(path), path


def test_required_knowledge_queries(tmp_path):
    items, _ = seeded(tmp_path)
    cases = {
        "EVS 입력 안 들어와": "EVS XT2 IN-A 입력 불량",
        "스트림덱 빨간불 들어오고 버튼이 안 먹어": "vMix 스트림덱 버튼 반응 불량",
        "CL3 페이더 내렸는데 소리가 계속 나가": "Yamaha CL3 페이더 떨림 및 송출 잔류",
        "다음 VCR이 첫 화면에서 멈춰": "vMix VCR 재생 멈춤",
    }
    for query, expected in cases.items():
        top_three = [item.title for _, item in semantic_search(query, items)]
        assert expected in top_three, (query, top_three)
        assert len(top_three) <= 3


def test_unrelated_question_returns_no_matches(tmp_path):
    items, _ = seeded(tmp_path)
    assert semantic_search("오늘 점심 메뉴 추천해줘", items) == []


def test_knowledge_crud(tmp_path):
    items, path = seeded(tmp_path)
    assert len(items) == 5
    data = {
        "title": "RTS KP12 마이크 레벨 점검",
        "context": "인터컴 마이크 레벨이 작게 들리는 상황.",
        "action": "KP12 패널 입력 게인과 매트릭스 라우팅을 확인한다.",
        "caution": "운영 중 전체 레벨을 급격히 올리지 말고 개별 패널부터 확인한다.",
    }
    db.add_knowledge_item(data, "[1, 0]", path)
    item = db.list_knowledge_items(path)[0]
    assert item.title == data["title"]
    data["context"] = "인터컴 마이크 레벨이 작거나 노이즈가 섞이는 상황."
    db.update_knowledge_item(item.id, data, "[0, 1]", path)
    updated = db.list_knowledge_items(path)[0]
    assert updated.context == data["context"]
    assert updated.embedding == "[0, 1]"
    db.delete_knowledge_item(item.id, path)
    assert len(db.list_knowledge_items(path)) == 5


def test_legacy_incident_rows_are_mapped_to_knowledge(tmp_path):
    path = tmp_path / "legacy.db"
    db.init_db(path)
    legacy = {
        "incident_number": "999",
        "equipment": "LEGACY",
        "symptom": "기존 증상",
        "cause": "기존 원인",
        "action": "기존 조치",
        "notes": "기존 비고",
    }
    db.add_incident(legacy, None, path)
    item = db.list_knowledge_items(path)[0]
    assert item.title == "LEGACY 기존 증상"
    assert item.context == "기존 증상"
    assert item.action == "기존 조치"
    assert "기존 원인" in item.caution
