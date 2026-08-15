import hmac
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

import storage as db
from ai_service import DISCLAIMER, analyze
from search import create_embedding, is_ambiguous, relevance_label, semantic_search
from styles import CSS

load_dotenv()
st.set_page_config(page_title="SPOTV Trouble AI", page_icon="📡", layout="wide", initial_sidebar_state="expanded")
st.markdown(CSS, unsafe_allow_html=True)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
PROTECTED_PAGES = {"장애이력 관리", "새 장애 등록", "시스템 정보"}
GOOGLE_LOGIN_ENABLED = os.getenv("ENABLE_GOOGLE_LOGIN", "false").lower() == "true"
ALLOWED_EMAILS = {
    email.strip().lower()
    for source in [os.getenv("ALLOWED_EMAILS", ""), os.getenv("ADDITIONAL_ALLOWED_EMAILS", "")]
    for email in source.replace(";", ",").split(",")
    if email.strip()
}


def require_user_access():
    if not GOOGLE_LOGIN_ENABLED:
        return
    if not st.user.is_logged_in:
        st.markdown('<div class="lock-card"><div class="lock-icon">🔐</div><h2>SPOTV Trouble AI 로그인</h2><p>등록된 팀원 Google 계정으로 로그인해 주세요.</p></div>', unsafe_allow_html=True)
        _, center, _ = st.columns([1, 1.15, 1])
        with center:
            st.button("Google 계정으로 로그인", type="primary", on_click=st.login, use_container_width=True)
        st.stop()
    email = str(getattr(st.user, "email", "")).strip().lower()
    if ALLOWED_EMAILS and email not in ALLOWED_EMAILS:
        st.error("이 Google 계정은 접근 권한이 없습니다.")
        st.caption(email)
        st.button("다른 계정으로 로그인", on_click=st.logout)
        st.stop()


require_user_access()
db.init_db()


def card(item, score, rank):
    st.markdown(f"""<div class="card"><span class="badge">{relevance_label(score, rank)}</span>
    <h3>사고번호 {item.incident_number} · {item.equipment}</h3>
    <div class="label">증상</div><div class="value">{item.symptom}</div>
    <div class="label">원인</div><div class="value">{item.cause}</div>
    <div class="label">조치</div><div class="value">{item.action}</div></div>""", unsafe_allow_html=True)


def incident_fields(prefix, item=None):
    number = st.text_input("사고번호", value=item.incident_number if item else "", key=f"{prefix}_number")
    occurred = st.text_input("발생일시 (선택)", value=(item.occurred_at or "") if item else "", placeholder="예: 2026-08-12 14:30", key=f"{prefix}_at")
    equipment = st.text_input("장비", value=item.equipment if item else "", key=f"{prefix}_equipment")
    symptom = st.text_area("증상", value=item.symptom if item else "", key=f"{prefix}_symptom")
    cause = st.text_area("원인", value=item.cause if item else "", key=f"{prefix}_cause")
    action = st.text_area("조치", value=item.action if item else "", key=f"{prefix}_action")
    notes = st.text_area("비고", value=item.notes if item else "", key=f"{prefix}_notes")
    return {"incident_number": number, "occurred_at": occurred or None, "equipment": equipment, "symptom": symptom, "cause": cause, "action": action, "notes": notes}


def valid(data):
    return all(data[x].strip() for x in ["incident_number", "equipment", "symptom", "cause", "action"])


def sidebar_brand():
    asset_dir = Path(__file__).with_name("assets")
    logo = next((path for name in ["sidebar_logo.svg", "sidebar_logo.png", "sidebar_logo.jpg", "sidebar_logo.jpeg", "sidebar_logo.webp"] if (path := asset_dir / name).exists()), None)
    if logo:
        st.image(str(logo), use_container_width=True)
    st.markdown("### SPOTV Trouble AI")


def require_admin_access():
    if st.session_state.get("admin_authenticated"):
        return True
    if not ADMIN_PASSWORD:
        st.error("관리자 비밀번호가 설정되지 않았습니다. ADMIN_PASSWORD 환경변수를 설정해 주세요.")
        return False
    st.markdown('<div class="lock-card"><div class="lock-icon">🔒</div><h2>관리자 전용 메뉴</h2><p>이 메뉴를 이용하려면 비밀번호를 입력해 주세요.</p></div>', unsafe_allow_html=True)
    _, center, _ = st.columns([1, 1.15, 1])
    with center:
        with st.form("admin_login"):
            password = st.text_input("비밀번호", type="password", autocomplete="current-password")
            submitted = st.form_submit_button("확인", type="primary")
        if submitted:
            if hmac.compare_digest(password, ADMIN_PASSWORD):
                st.session_state.admin_authenticated = True
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다.")
    return False


with st.sidebar:
    sidebar_brand()
    if GOOGLE_LOGIN_ENABLED and st.user.is_logged_in:
        st.caption(f"👤 {getattr(st.user, 'email', '')}")
    page = st.radio(
        "메뉴",
        ["AI 장애 검색", "장애이력 관리", "새 장애 등록", "시스템 정보"],
        key="main_navigation_v2",
        label_visibility="collapsed",
    )
    st.caption("Broadcast Engineering Knowledge System")
    if st.session_state.get("admin_authenticated") and st.button("관리자 로그아웃"):
        st.session_state.admin_authenticated = False
        st.rerun()
    if GOOGLE_LOGIN_ENABLED and st.user.is_logged_in:
        st.button("Google 로그아웃", on_click=st.logout)

if page in PROTECTED_PAGES and not require_admin_access():
    st.stop()

if page == "AI 장애 검색":
    st.markdown('<div class="hero"><div class="kicker">AI-powered Broadcast Engineering Knowledge System</div><h1>SPOTV Trouble AI</h1><p class="sub">과거 장애이력을 기반으로 방송 시스템 문제 해결을 지원합니다.</p></div>', unsafe_allow_html=True)
    total, _, updated = db.stats()
    cols = st.columns(2)
    for col, label, value in zip(cols, ["등록 장애", "최근 업데이트"], [total, "오늘" if updated[:10] == datetime.now().strftime("%Y-%m-%d") else updated[:10]]):
        col.markdown(f'<div class="metric"><span>{label}</span><strong>{value}</strong></div>', unsafe_allow_html=True)
    st.write("")
    with st.form("incident_search", border=False):
        query = st.text_input("현장 증상을 입력하세요", key="query", placeholder="예: EVS 입력이 안 들어와 / vMix 버튼이 반응 안 함", label_visibility="collapsed")
        search_submitted = st.form_submit_button("AI 장애 분석", type="primary")
    if search_submitted:
        if not query.strip():
            st.warning("증상을 입력해 주세요.")
        else:
            incidents = db.list_incidents()
            results = semantic_search(query, incidents) if incidents else []
            if is_ambiguous(query):
                st.markdown('<div class="notice"><b>현재 증상만으로는 범위가 넓습니다.</b><br>입력 신호, 출력, 녹화·재생, 오디오 중 어느 문제인지 함께 입력하면 더 정확하게 찾을 수 있습니다.</div>', unsafe_allow_html=True)
            top = results[0][1] if results else None
            if results:
                score, top = results[0]
                st.markdown("## 가장 유사한 과거 사례")
                card(top, score, 0)
            related_results = results[1:] if results else []
            analysis, checks = analyze(query, top)
            st.markdown("## AI 분석")
            st.write(analysis)
            st.markdown("### 우선 점검 권장사항")
            for idx, check in enumerate(checks, 1): st.write(f"{idx}. {check}")
            st.markdown(f'<div class="notice"><b>주의사항</b><br>{DISCLAIMER}</div>', unsafe_allow_html=True)
            if related_results:
                st.markdown("## 관련 과거 사례 TOP 3")
                for rank, (similarity, item) in enumerate(related_results, 1): card(item, similarity, rank)

elif page == "장애이력 관리":
    st.title("장애이력 관리")
    st.caption("등록된 사고를 수정하거나 삭제할 수 있습니다. 수정 시 검색 데이터도 갱신됩니다.")
    for item in db.list_incidents():
        with st.expander(f"{item.incident_number} · {item.equipment} · {item.symptom}"):
            with st.form(f"edit_{item.id}"):
                data = incident_fields(f"edit_{item.id}", item)
                save = st.form_submit_button("수정 저장")
                if save:
                    if not valid(data): st.error("필수 항목을 모두 입력해 주세요.")
                    else:
                        try:
                            embedding = create_embedding(" ".join([data["equipment"], data["symptom"], data["cause"], data["action"], data["notes"]]))
                            db.update_incident(item.id, data, embedding)
                            st.success("장애이력이 수정되었습니다.")
                            st.rerun()
                        except (sqlite3.IntegrityError, ValueError) as exc: st.error(str(exc) or "이미 사용 중인 사고번호입니다.")
            if st.button("삭제", key=f"delete_{item.id}"):
                db.delete_incident(item.id); st.rerun()

elif page == "새 장애 등록":
    st.title("새 장애 등록")
    with st.form("new_incident", clear_on_submit=True):
        data = incident_fields("new")
        submitted = st.form_submit_button("장애이력 등록", type="primary")
        if submitted:
            if not valid(data): st.error("필수 항목을 모두 입력해 주세요.")
            else:
                try:
                    embedding = create_embedding(" ".join([data["equipment"], data["symptom"], data["cause"], data["action"], data["notes"]]))
                    db.add_incident(data, embedding)
                    st.success("장애이력이 정상적으로 등록되었습니다.")
                except (sqlite3.IntegrityError, ValueError) as exc: st.error(str(exc) or "이미 사용 중인 사고번호입니다.")

else:
    st.title("시스템 정보")
    st.markdown("""**검색 모드**  
OpenAI API 키와 임베딩이 있으면 OpenAI 의미 검색을 사용하며, 그렇지 않으면 개인정보를 외부로 보내지 않는 로컬 유사도 검색으로 자동 전환합니다.

**데이터 저장**  
Cloud Run에서는 장애이력이 Firestore에 저장됩니다. 로컬 실행 시에는 `spotv_trouble.db`를 사용합니다.

**보안**  
API 키는 `.env`에서만 읽으며 코드와 DB에는 저장하지 않습니다.""")
