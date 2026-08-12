import os


DISCLAIMER = "과거 장애사례와 제조사 매뉴얼을 기반으로 한 참고 정보이며 현재 장애 원인을 확정하는 것은 아닙니다."


def fallback_analysis(query, incident=None, manual_matches=None):
    manual_matches = manual_matches or []
    if incident:
        analysis = (f"입력하신 ‘{query}’ 증상은 과거 사고번호 {incident.incident_number}의 "
                    f"‘{incident.symptom}’ 사례와 장비 또는 증상 표현이 유사합니다. 당시에는 "
                    f"{incident.cause}이(가) 확인되었지만, 현재 장애도 같은 원인이라고 단정할 수 없습니다.")
    else:
        analysis = f"입력하신 ‘{query}’ 증상과 관련된 과거 장애이력은 충분하지 않습니다."
    if manual_matches:
        source = manual_matches[0]
        analysis += (f" 장비 매뉴얼 ‘{source.get('title', '')}’ {source.get('page_number', '-')}페이지의 "
                     "관련 항목도 함께 확인해 주세요.")
    checks = [
        "영향 범위와 현재 입·출력 상태를 먼저 기록합니다.",
        "신호원, 케이블, 전원 및 물리 연결 상태를 확인합니다.",
        "라우팅과 장비 설정이 정상인지 확인합니다.",
        "가능하면 정상 포트·케이블·신호원으로 교차 점검합니다.",
        "위 항목이 정상이면 검색된 과거 사례와 매뉴얼의 점검 절차를 비교합니다.",
        "변경 전 상태를 기록하고 제조사 안전 절차에 따라 단계별로 조치합니다.",
    ]
    return analysis, checks


def analyze(query, incident=None, manual_matches=None):
    manual_matches = manual_matches or []
    try:
        from openai import OpenAI
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError
        incident_context = "과거 장애이력 없음"
        if incident:
            incident_context = f"""과거 장비: {incident.equipment}
과거 증상: {incident.symptom}
과거 원인: {incident.cause}
과거 조치: {incident.action}"""
        manual_context = "\n\n".join(
            f"매뉴얼: {item.get('title', '')}, 페이지 {item.get('page_number', '-')}: {item.get('content', '')[:1800]}"
            for item in manual_matches[:3]
        ) or "매뉴얼 검색 결과 없음"
        prompt = f"""당신은 방송 기술 장애 대응 보조자다. 원인을 확정하지 말고 과거 사례와 제조사 매뉴얼을 구분하여 3~6단계 점검 순서를 한국어로 작성하라. 매뉴얼에 없는 내용을 만들어내지 마라.
현재 증상: {query}
{incident_context}
{manual_context}
형식: 첫 문단은 분석, 이후 각 줄은 '- '로 시작하는 점검 순서."""
        response = OpenAI().responses.create(model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini"), input=prompt)
        lines = response.output_text.strip().splitlines()
        checks = [x[2:].strip() for x in lines if x.strip().startswith("- ")]
        analysis = " ".join(x.strip() for x in lines if not x.strip().startswith("- "))
        return (analysis, checks) if analysis and checks else fallback_analysis(query, incident, manual_matches)
    except Exception:
        return fallback_analysis(query, incident, manual_matches)
