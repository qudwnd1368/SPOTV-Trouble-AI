import base64
import html
import hmac
import logging
import mimetypes
import os
from urllib.parse import quote
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

import storage as db
from ai_service import DISCLAIMER, answer_general_question, answer_intro
from search import create_knowledge_embedding, relevance_label, semantic_search
from styles import CSS

APP_NAME = "SPOTV Tech Copilot"
APP_SUBTITLE = "AI 기반 방송기술 지식 · 인수인계 지원 시스템"
PROTECTED_PAGES = {"기술 지식 관리", "시스템 정보"}
NAV_OPTIONS = ["AI 질문", "기술 지식 관리", "시스템 정보"]
NAV_KEY = "main_navigation_v3"

load_dotenv()
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(levelname)s:%(name)s:%(message)s",
)

st.set_page_config(page_title=APP_NAME, page_icon="📡", layout="wide", initial_sidebar_state="expanded")
st.markdown(CSS, unsafe_allow_html=True)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
GOOGLE_LOGIN_ENABLED = os.getenv("ENABLE_GOOGLE_LOGIN", "false").lower() == "true"
ALLOWED_EMAILS = {
    email.strip().lower()
    for source in [os.getenv("ALLOWED_EMAILS", ""), os.getenv("ADDITIONAL_ALLOWED_EMAILS", "")]
    for email in source.replace(";", ",").split(",")
    if email.strip()
}


def safe(value):
    return html.escape(str(value or ""))


def short(value, limit=90):
    text = str(value or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def require_user_access():
    if not GOOGLE_LOGIN_ENABLED:
        return
    if not st.user.is_logged_in:
        st.markdown(f'<div class="lock-card"><div class="lock-icon">🔐</div><h2>{APP_NAME} 로그인</h2><p>등록된 팀원 Google 계정으로 로그인해 주세요.</p></div>', unsafe_allow_html=True)
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


def image_data_uri(path):
    mime_type = mimetypes.guess_type(path.name)[0] or "image/svg+xml"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def sidebar_brand():
    asset_dir = Path(__file__).with_name("assets")
    logo = next((path for name in ["sidebar_logo.svg", "sidebar_logo.png", "sidebar_logo.jpg", "sidebar_logo.jpeg", "sidebar_logo.webp"] if (path := asset_dir / name).exists()), None)
    home_href = f"?page={quote(NAV_OPTIONS[0])}"
    if logo:
        st.markdown(
            f'<a class="sidebar-logo-link" href="{home_href}" target="_self" title="메인 화면으로 이동">'
            f'<img src="{image_data_uri(logo)}" alt="{safe(APP_NAME)}"></a>',
            unsafe_allow_html=True,
        )
    st.markdown(f'<a class="sidebar-brand-link" href="{home_href}" target="_self">{safe(APP_NAME)}</a>', unsafe_allow_html=True)
    st.markdown(f'<div class="sidebar-subtitle">{safe(APP_SUBTITLE)}</div>', unsafe_allow_html=True)


def knowledge_card(item, score=None, rank=0):
    badge = relevance_label(score, rank) if score is not None else "기술 지식"
    st.markdown(f"""<div class="card knowledge-card"><span class="badge">{safe(badge)}</span>
    <h3>{safe(item.title)}</h3>
    <div class="label">상황</div><div class="value">{safe(item.context)}</div>
    <div class="label">조치</div><div class="value">{safe(item.action)}</div>
    <div class="label">주의사항</div><div class="value">{safe(item.caution)}</div></div>""", unsafe_allow_html=True)


def knowledge_fields(prefix, item=None):
    title = st.text_input("제목", value=item.title if item else "", placeholder="예: vMix VCR 재생 멈춤", key=f"{prefix}_title")
    context = st.text_area("상황", value=item.context if item else "", placeholder="어떤 상황에서 문제가 발생했거나 작업이 필요한지 적어주세요.", key=f"{prefix}_context")
    action = st.text_area("조치", value=item.action if item else "", placeholder="실제로 해결했거나 작업했던 방법을 적어주세요.", key=f"{prefix}_action")
    caution = st.text_area("주의사항", value=item.caution if item else "", placeholder="다시 발생했을 때 반드시 알아야 할 내용을 적어주세요.", key=f"{prefix}_caution")
    return {"title": title, "context": context, "action": action, "caution": caution}


def valid_knowledge(data):
    return all(data[key].strip() for key in ["title", "context", "action", "caution"])


def save_embedding(data):
    return create_knowledge_embedding(data)


def render_recent(items):
    st.markdown("## 최근 기술 지식")
    if not items:
        st.info("아직 등록된 기술 지식이 없습니다.")
        return
    for item in items[:5]:
        with st.expander(item.title):
            st.markdown(f"**상황**  \n{item.context}")
            st.markdown(f"**조치**  \n{item.action}")
            st.markdown(f"**주의사항**  \n{item.caution}")


def render_search_page():
    st.markdown(f'<div class="hero"><div class="kicker">{safe(APP_SUBTITLE)}</div><h1>{safe(APP_NAME)}</h1><p class="sub">방송기술 업무 중 궁금한 내용을 질문하세요.</p></div>', unsafe_allow_html=True)
    items = db.list_knowledge_items()
    total, _, updated = db.stats()
    cols = st.columns(2)
    updated_label = "오늘" if updated[:10] == datetime.now().strftime("%Y-%m-%d") else updated[:10]
    for col, label, value in zip(cols, ["등록 기술 지식", "최근 업데이트"], [total, updated_label]):
        col.markdown(f'<div class="metric"><span>{label}</span><strong>{safe(value)}</strong></div>', unsafe_allow_html=True)

    st.write("")
    with st.form("knowledge_search", border=False):
        left, right = st.columns([5, 1])
        with left:
            query = st.text_input("질문", key="query", placeholder="예: vMix에서 다음 영상으로 넘어갈 때 멈추는데 버튼을 빠르게 눌렀던 것 같아.", label_visibility="collapsed")
        with right:
            submitted = st.form_submit_button("질문하기", type="primary", use_container_width=True)

    if submitted:
        if not query.strip():
            st.warning("질문을 입력해 주세요.")
        else:
            results = semantic_search(query, items, limit=3) if items else []
            st.markdown("## AI 답변")
            st.write(answer_intro(results))
            if results:
                st.markdown("## 관련 기술 지식")
                for rank, (score, item) in enumerate(results):
                    knowledge_card(item, score, rank)
            else:
                with st.spinner("일반 AI 답변을 생성하는 중입니다."):
                    general_answer = answer_general_question(query)
                    st.markdown(general_answer.text)
                    if general_answer.model:
                        st.caption(f"사용 모델: {general_answer.model}")
            st.markdown(f'<div class="notice"><b>주의사항</b><br>{safe(DISCLAIMER)}</div>', unsafe_allow_html=True)

    render_recent(items)


def render_knowledge_management():
    st.title("기술 지식 관리")
    st.caption("방송기술 업무 중 발생한 문제 해결 경험, 장비 작업 방법, 주의사항, 인수인계 노하우를 관리합니다.")

    with st.expander("신규 기술 지식 등록", expanded=False):
        with st.form("new_knowledge", clear_on_submit=True):
            data = knowledge_fields("new")
            submitted = st.form_submit_button("등록", type="primary")
            if submitted:
                if not valid_knowledge(data):
                    st.error("제목, 상황, 조치, 주의사항을 모두 입력해 주세요.")
                else:
                    db.add_knowledge_item(data, save_embedding(data))
                    st.success("기술 지식이 등록되었습니다.")
                    st.rerun()

    items = db.list_knowledge_items()
    title_query = st.text_input("제목 검색", placeholder="찾고 싶은 제목 일부를 입력하세요.")
    if title_query.strip():
        needle = title_query.strip().lower()
        items = [item for item in items if needle in item.title.lower()]

    st.markdown("### 기술 지식 목록")
    if not items:
        st.info("표시할 기술 지식이 없습니다.")
        return

    for item in items:
        with st.expander(item.title):
            st.markdown(f"""<div class="table-card">
            <div><b>제목</b><br>{safe(item.title)}</div>
            <div><b>상황</b><br>{safe(short(item.context, 120))}</div>
            <div><b>조치</b><br>{safe(short(item.action, 120))}</div>
            <div><b>주의사항</b><br>{safe(short(item.caution, 120))}</div>
            </div>""", unsafe_allow_html=True)
            st.markdown("#### 전체 내용 및 수정")
            with st.form(f"edit_{item.id}"):
                data = knowledge_fields(f"edit_{item.id}", item)
                save = st.form_submit_button("수정 저장")
                if save:
                    if not valid_knowledge(data):
                        st.error("제목, 상황, 조치, 주의사항을 모두 입력해 주세요.")
                    else:
                        db.update_knowledge_item(item.id, data, save_embedding(data))
                        st.success("기술 지식이 수정되었습니다.")
                        st.rerun()
            if st.button("삭제", key=f"delete_{item.id}"):
                db.delete_knowledge_item(item.id)
                st.rerun()


def render_system_info():
    st.title("시스템 정보")
    st.markdown(f"""**프로젝트명**<br>
{APP_NAME}

**목적**<br>
방송기술 업무 중 발생하는 문제 해결 경험과 작업 노하우를 간단히 축적하고, 필요할 때 AI에게 질문하여 과거 인수인계 내용을 즉시 찾아보는 시스템입니다.

**데이터 구조**<br>
사용자에게 보이는 기술 지식은 `제목`, `상황`, `조치`, `주의사항` 네 가지 핵심 항목으로 구성됩니다.

**검색 모드**<br>
OpenAI API 키와 임베딩이 있으면 OpenAI 의미 검색을 사용하며, 그렇지 않으면 개인정보를 외부로 보내지 않는 로컬 유사도 검색으로 자동 전환합니다.

**데이터 저장**  
Cloud Run에서는 기술 지식이 Firestore에 저장됩니다. 로컬 실행 시에는 `spotv_trouble.db`를 사용합니다.

**보안**  
API 키와 비밀번호는 환경변수 또는 Secret Manager에서만 읽으며 코드와 DB에는 저장하지 않습니다.""")


require_user_access()
db.init_db()

query_page = st.query_params.get("page")
if isinstance(query_page, list):
    query_page = query_page[0] if query_page else None
if query_page in NAV_OPTIONS:
    st.session_state[NAV_KEY] = query_page


def sync_navigation_query():
    st.query_params["page"] = st.session_state[NAV_KEY]


with st.sidebar:
    sidebar_brand()
    if GOOGLE_LOGIN_ENABLED and st.user.is_logged_in:
        st.caption(f"👤 {getattr(st.user, 'email', '')}")
    page = st.radio(
        "메뉴",
        NAV_OPTIONS,
        key=NAV_KEY,
        label_visibility="collapsed",
        on_change=sync_navigation_query,
    )
    if st.session_state.get("admin_authenticated") and st.button("관리자 로그아웃"):
        st.session_state.admin_authenticated = False
        st.rerun()
    if GOOGLE_LOGIN_ENABLED and st.user.is_logged_in:
        st.button("Google 로그아웃", on_click=st.logout)

if page in PROTECTED_PAGES and not require_admin_access():
    st.stop()

if page == "AI 질문":
    render_search_page()
elif page == "기술 지식 관리":
    render_knowledge_management()
else:
    render_system_info()
