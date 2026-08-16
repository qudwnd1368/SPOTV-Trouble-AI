DISCLAIMER = "저장된 기술 지식을 기반으로 한 참고 정보입니다. 실제 작업 전 현장 상태와 방송 영향 범위를 반드시 확인하세요."
NO_MATCH_MESSAGE = "현재 등록된 기술 지식에서는 관련 사례를 찾지 못했습니다."
FOUND_MESSAGE = "관련된 과거 기술 지식을 찾았습니다."


def answer_intro(matches):
    return FOUND_MESSAGE if matches else NO_MATCH_MESSAGE
