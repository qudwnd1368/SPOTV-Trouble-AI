import logging
import os


logger = logging.getLogger(__name__)

DISCLAIMER = "AI 답변은 참고 정보입니다. 실제 작업 전 장비 모델, 소프트웨어 버전, 현장 라우팅, 방송 영향 범위를 반드시 확인하세요."
NO_MATCH_MESSAGE = "현재 등록된 기술 지식에서는 관련 사례를 찾지 못했습니다. 일반 AI 답변으로 안내합니다."
FOUND_MESSAGE = "관련된 과거 기술 지식을 찾았습니다."
NO_AI_CONFIG_MESSAGE = "일반 AI 답변을 사용하려면 OPENAI_API_KEY 환경변수가 필요합니다."


def answer_intro(matches):
    return FOUND_MESSAGE if matches else NO_MATCH_MESSAGE


def answer_general_question(query):
    if not os.getenv("OPENAI_API_KEY"):
        return NO_AI_CONFIG_MESSAGE
    try:
        from openai import OpenAI

        prompt = f"""당신은 방송기술 엔지니어를 돕는 SPOTV Tech Copilot입니다.
사용자가 묻는 장비 운용, 설정, 점검, 문제 해결 질문에 한국어로 답하세요.

답변 원칙:
- 저장된 내부 사례가 없을 때 제공하는 일반 AI 답변입니다.
- 없는 사실을 확정하지 말고, 모델/펌웨어/현장 구성에 따라 달라질 수 있으면 그 점을 짧게 말하세요.
- 가능한 경우 작업 순서, 확인할 메뉴, 주의사항을 나눠서 설명하세요.
- 방송 중 조작 위험이 있으면 사전 테스트와 백업/원복 방법 확인을 안내하세요.
- 사용자가 바로 따라 할 수 있게 간결하고 실무적으로 답하세요.

질문:
{query}"""
        response = OpenAI().responses.create(
            model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini"),
            input=prompt,
        )
        return response.output_text.strip() or "일반 AI 답변을 생성하지 못했습니다."
    except Exception:
        logger.exception("General AI answer failed.")
        return "일반 AI 답변 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
