import ai_service
import database as db
from models import KnowledgeItem
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


def test_unknown_broadcast_equipment_question_returns_no_matches(tmp_path):
    items, _ = seeded(tmp_path)
    assert semantic_search("mvs3000 스위처 pip 어떻게 설정해?", items) == []


def test_general_ai_answer_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    answer = ai_service.answer_general_question("mvs3000 스위처 pip 어떻게 설정해?")
    assert "OPENAI_API_KEY" in answer.text
    assert answer.model == ""
    assert not answer.ok


def test_candidate_models_prefers_configured_model(monkeypatch):
    monkeypatch.setenv("OPENAI_CHAT_MODEL", "custom-model")
    assert tuple(ai_service._candidate_models()) == ("custom-model", "gpt-5.6-luna", "gpt-4o-mini")


def test_general_answer_includes_model_name():
    answer = ai_service.GeneralAnswer(text="답변", model="gpt-5.6-luna", ok=True)
    assert answer.text == "답변"
    assert answer.model == "gpt-5.6-luna"
    assert answer.ok


def test_equipment_title_match_ranks_first():
    items = [
        KnowledgeItem(
            id=1,
            title="EVS XT-2 아날로그 오디오 입력 및 출력 불량",
            context="아날로그 오디오 입력 및 출력 불량",
            action="오디오 코덱보드 구매 후 정상동작 확인",
            caution="오디오 코덱보드 불량",
        ),
        KnowledgeItem(
            id=2,
            title="오디오콘솔 페이더 올려도 소리가 안나옴",
            context="오디오콘솔 페이더 올려도 소리가 안나옴",
            action="AUX로 되어있거나 17-32 등 다른 레이어로 페이지가 이동되어있었음",
            caution="타이틀 들어가기전 반드시 레이어와 FADER/AUX 선택 확인",
        ),
        KnowledgeItem(
            id=3,
            title="YAMAHA CL3 페이더를 내려도 소리가 송출되고 9-16번 페이더가 덜덜거림",
            context="페이더를 내려도 소리가 송출되고 9-16번 페이더가 덜덜거림",
            action="9-16번 페이더 교체",
            caution="페이더 모터 불량",
        ),
    ]
    results = semantic_search("오디오콘솔 소리안나와", items)
    assert [item.title for _, item in results] == ["오디오콘솔 페이더 올려도 소리가 안나옴"]


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
