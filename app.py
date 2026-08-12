import hmac
import html
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

import storage as db
from ai_service import DISCLAIMER, analyze
from manual_index import download_drive_pdf, index_pdf_bytes, list_drive_manuals
from search import create_embedding, is_ambiguous, manual_search, relevance_label, semantic_search
from styles import CSS

load_dotenv()
st.set_page_config(page_title="SPOTV Trouble AI", page_icon="📡", layout="wide", initial_sidebar_state="expanded")
st.markdown(CSS, unsafe_allow_html=True)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
PROTECTED_PAGES = {"장애이력 관리", "새 장애 등록", "매뉴얼 관리", "시스템 정보"}
GOOGLE_LOGIN_ENABLED = os.getenv("ENABLE_GOOGLE_LOGIN", "false").lower() == "true"
ALLOWED_EMAILS = {email.strip().lower() for email in os.getenv("ALLOWED_EMAILS", "").split(",") if email.strip()}


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


def manual_card(item, score):
    title = html.escape(str(item.get("title", "장비 매뉴얼")))
    content = html.escape(str(item.get("content", "")))
    page_number = item.get("page_number", "-")
    url = item.get("drive_url", "")
    source = f'<a href="{html.escape(url)}" target="_blank">원문 열기</a>' if url else "업로드된 매뉴얼"
    st.markdown(f"""<div class="card manual-card"><span class="badge">매뉴얼 근거</span>
    <h3>{title} · {page_number}페이지</h3>
    <div class="value">{content}</div><div class="manual-source">관련도 {score:.2f} · {source}</div></div>""",
                unsafe_allow_html=True)


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
        ["AI 장애 검색", "장애이력 관리", "새 장애 등록", "매뉴얼 관리", "시스템 정보"],
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
    manual_total, manual_pages, _ = db.manual_stats()
    cols = st.columns(3)
    for col, label, value in zip(cols, ["등록 장애", "색인 매뉴얼", "최근 업데이트"], [total, manual_total, "오늘" if updated[:10] == datetime.now().strftime("%Y-%m-%d") else updated[:10]]):
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
            manual_results = manual_search(query, db.list_manual_chunks())
            if is_ambiguous(query):
                st.markdown('<div class="notice"><b>현재 증상만으로는 범위가 넓습니다.</b><br>입력 신호, 출력, 녹화·재생, 오디오 중 어느 문제인지 함께 입력하면 더 정확하게 찾을 수 있습니다.</div>', unsafe_allow_html=True)
            top = results[0][1] if results else None
            if results:
                score, top = results[0]
                st.markdown("## 가장 유사한 과거 사례")
                card(top, score, 0)
            analysis, checks = analyze(query, top, [item for _, item in manual_results])
            st.markdown("## AI 분석")
            st.write(analysis)
            st.markdown("### 우선 점검 권장사항")
            for idx, check in enumerate(checks, 1): st.write(f"{idx}. {check}")
            st.markdown(f'<div class="notice"><b>주의사항</b><br>{DISCLAIMER}</div>', unsafe_allow_html=True)
            if manual_results:
                st.markdown("## 관련 장비 매뉴얼")
                for similarity, item in manual_results:
                    manual_card(item, similarity)
            else:
                st.info("검색 가능한 매뉴얼 색인이 없습니다. 관리자가 매뉴얼 관리 메뉴에서 색인할 수 있습니다.")
            if results:
                st.markdown("## 관련 과거 사례 TOP 3")
                for rank, (similarity, item) in enumerate(results): card(item, similarity, rank)

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

elif page == "매뉴얼 관리":
    st.title("장비 매뉴얼 관리")
    st.caption("공유 Google Drive 폴더 또는 직접 업로드한 PDF를 페이지별로 색인합니다. 색인 후에는 원본과 별도로 검색 데이터가 유지됩니다.")
    manual_total, manual_pages, manual_chunks = db.manual_stats()
    cols = st.columns(3)
    for col, label, value in zip(cols, ["색인 매뉴얼", "전체 페이지", "검색 조각"], [manual_total, manual_pages, manual_chunks]):
        col.metric(label, value)

    st.subheader("Google Drive 공유 폴더")
    sources, source_mode = list_drive_manuals()
    st.caption(f"{source_mode} · PDF {len(sources)}개 확인")
    with st.expander("확인된 파일 목록"):
        for source in sources:
            st.write(f"• {source['name']}")
    force_sync = st.checkbox("이미 색인된 파일도 다시 색인", value=False)
    if st.button("Drive 폴더 색인 동기화", type="primary"):
        existing = {item.get("drive_file_id") for item in db.list_manuals()}
        progress = st.progress(0, text="매뉴얼 동기화를 시작합니다.")
        successes, skipped, failures = [], [], []
        for index, source in enumerate(sources, 1):
            progress.progress((index - 1) / max(1, len(sources)), text=f"{source['name']} 내려받는 중")
            if source["id"] in existing and not force_sync:
                skipped.append(source["name"])
                continue
            try:
                pdf_bytes = download_drive_pdf(source["id"])
                metadata = index_pdf_bytes(pdf_bytes, source["name"], db, source["id"], source["url"])
                successes.append(f"{metadata['title']} ({metadata['page_count']}페이지)")
            except Exception as exc:
                failures.append(f"{source['name']}: {exc}")
        progress.progress(1.0, text="동기화가 완료되었습니다.")
        if successes:
            st.success("색인 완료: " + ", ".join(successes))
        if skipped:
            st.info(f"기존 색인 {len(skipped)}개는 건너뛰었습니다.")
        if failures:
            st.error("\n".join(failures))
        if successes:
            st.rerun()

    st.subheader("PDF 직접 등록")
    uploads = st.file_uploader("장비 매뉴얼 PDF", type=["pdf"], accept_multiple_files=True)
    if uploads and st.button("업로드한 PDF 색인"):
        completed, failures = [], []
        for uploaded in uploads:
            try:
                metadata = index_pdf_bytes(uploaded.getvalue(), uploaded.name, db)
                completed.append(f"{metadata['title']} ({metadata['page_count']}페이지)")
            except Exception as exc:
                failures.append(f"{uploaded.name}: {exc}")
        if completed:
            st.success("색인 완료: " + ", ".join(completed))
        if failures:
            st.error("\n".join(failures))
        if completed:
            st.rerun()

    st.subheader("색인된 매뉴얼")
    manuals = db.list_manuals()
    if not manuals:
        st.info("아직 색인된 매뉴얼이 없습니다.")
    for manual in manuals:
        left, right = st.columns([5, 1])
        with left:
            title = manual.get("title", "")
            pages = manual.get("page_count", 0)
            chunks = manual.get("chunk_count", 0)
            st.write(f"**{title}** · {pages}페이지 · 검색 조각 {chunks}개")
            if manual.get("drive_url"):
                st.caption(manual["drive_url"])
        with right:
            if st.button("색인 삭제", key=f"delete_manual_{manual.get('id')}"):
                db.delete_manual(manual.get("id"))
                st.rerun()

else:
    st.title("시스템 정보")
    st.markdown("""**검색 모드**  
OpenAI API 키와 임베딩이 있으면 OpenAI 의미 검색을 사용하며, 그렇지 않으면 개인정보를 외부로 보내지 않는 로컬 유사도 검색으로 자동 전환합니다.

**데이터 저장**  
Cloud Run에서는 장애이력과 매뉴얼 색인이 Firestore에 저장됩니다. 로컬 실행 시에는 `spotv_trouble.db`를 사용합니다.

**매뉴얼 검색**  
PDF에서 페이지별 텍스트를 추출하여 무료 로컬 유사도 검색으로 조회합니다. 검색 결과에는 매뉴얼명과 원문 페이지가 표시됩니다.

**보안**  
API 키는 `.env`에서만 읽으며 코드와 DB에는 저장하지 않습니다.""")
