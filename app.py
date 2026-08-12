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
st.set_page_config(page_title="SPOTV Trouble AI", page_icon="ğŸ“¡", layout="wide", initial_sidebar_state="expanded")
st.markdown(CSS, unsafe_allow_html=True)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
PROTECTED_PAGES = {"ì¥ì• ì´ë ¥ ê´€ë¦¬", "ìƒˆ ì¥ì•  ë“±ë¡", "ë§¤ë‰´ì–¼ ê´€ë¦¬", "ì‹œìŠ¤í…œ ì •ë³´"}
GOOGLE_LOGIN_ENABLED = os.getenv("ENABLE_GOOGLE_LOGIN", "false").lower() == "true"
ALLOWED_EMAILS = {email.strip().lower() for email in os.getenv("ALLOWED_EMAILS", "").split(",") if email.strip()}


def require_user_access():
    if not GOOGLE_LOGIN_ENABLED:
        return
    if not st.user.is_logged_in:
        st.markdown('<div class="lock-card"><div class="lock-icon">ğŸ”</div><h2>SPOTV Trouble AI ë¡œê·¸ì¸</h2><p>ë“±ë¡ëœ íŒ€ì› Google ê³„ì •ìœ¼ë¡œ ë¡œê·¸ì¸í•´ ì£¼ì„¸ìš”.</p></div>', unsafe_allow_html=True)
        _, center, _ = st.columns([1, 1.15, 1])
        with center:
            st.button("Google ê³„ì •ìœ¼ë¡œ ë¡œê·¸ì¸", type="primary", on_click=st.login, use_container_width=True)
        st.stop()
    email = str(getattr(st.user, "email", "")).strip().lower()
    if ALLOWED_EMAILS and email not in ALLOWED_EMAILS:
        st.error("ì´ Google ê³„ì •ì€ ì ‘ê·¼ ê¶Œí•œì´ ì—†ìŠµë‹ˆë‹¤.")
        st.caption(email)
        st.button("ë‹¤ë¥¸ ê³„ì •ìœ¼ë¡œ ë¡œê·¸ì¸", on_click=st.logout)
        st.stop()


require_user_access()
db.init_db()


def card(item, score, rank):
    st.markdown(f"""<div class="card"><span class="badge">{relevance_label(score, rank)}</span>
    <h3>ì‚¬ê³ ë²ˆí˜¸ {item.incident_number} Â· {item.equipment}</h3>
    <div class="label">ì¦ìƒ</div><div class="value">{item.symptom}</div>
    <div class="label">ì›ì¸</div><div class="value">{item.cause}</div>
    <div class="label">ì¡°ì¹˜</div><div class="value">{item.action}</div></div>""", unsafe_allow_html=True)


def manual_card(item, score):
    title = html.escape(str(item.get("title", "ì¥ë¹„ ë§¤ë‰´ì–¼")))
    content = html.escape(str(item.get("content", "")))
    page_number = item.get("page_number", "-")
    url = item.get("drive_url", "")
    source = f'<a href="{html.escape(url)}" target="_blank">ì›ë¬¸ ì—´ê¸°</a>' if url else "ì—…ë¡œë“œëœ ë§¤ë‰´ì–¼"
    st.markdown(f"""<div class="card manual-card"><span class="badge">ë§¤ë‰´ì–¼ ê·¼ê±°</span>
    <h3>{title} Â· {page_number}í˜ì´ì§€</h3>
    <div class="value">{content}</div><div class="manual-source">ê´€ë ¨ë„ {score:.2f} Â· {source}</div></div>""",
                unsafe_allow_html=True)


def incident_fields(prefix, item=None):
    number = st.text_input("ì‚¬ê³ ë²ˆí˜¸", value=item.incident_number if item else "", key=f"{prefix}_number")
    occurred = st.text_input("ë°œìƒì¼ì‹œ (ì„ íƒ)", value=(item.occurred_at or "") if item else "", placeholder="ì˜ˆ: 2026-08-12 14:30", key=f"{prefix}_at")
    equipment = st.text_input("ì¥ë¹„", value=item.equipment if item else "", key=f"{prefix}_equipment")
    symptom = st.text_area("ì¦ìƒ", value=item.symptom if item else "", key=f"{prefix}_symptom")
    cause = st.text_area("ì›ì¸", value=item.cause if item else "", key=f"{prefix}_cause")
    action = st.text_area("ì¡°ì¹˜", value=item.action if item else "", key=f"{prefix}_action")
    notes = st.text_area("ë¹„ê³ ", value=item.notes if item else "", key=f"{prefix}_notes")
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
        st.error("ê´€ë¦¬ì ë¹„ë°€ë²ˆí˜¸ê°€ ì„¤ì •ë˜ì§€ ì•Šì•˜ìŠµë‹ˆë‹¤. ADMIN_PASSWORD í™˜ê²½ë³€ìˆ˜ë¥¼ ì„¤ì •í•´ ì£¼ì„¸ìš”.")
        return False
    st.markdown('<div class="lock-card"><div class="lock-icon">ğŸ”’</div><h2>ê´€ë¦¬ì ì „ìš© ë©”ë‰´</h2><p>ì´ ë©”ë‰´ë¥¼ ì´ìš©í•˜ë ¤ë©´ ë¹„ë°€ë²ˆí˜¸ë¥¼ ì…ë ¥í•´ ì£¼ì„¸ìš”.</p></div>', unsafe_allow_html=True)
    _, center, _ = st.columns([1, 1.15, 1])
    with center:
        with st.form("admin_login"):
            password = st.text_input("ë¹„ë°€ë²ˆí˜¸", type="password", autocomplete="current-password")
            submitted = st.form_submit_button("í™•ì¸", type="primary")
        if submitted:
            if hmac.compare_digest(password, ADMIN_PASSWORD):
                st.session_state.admin_authenticated = True
                st.rerun()
            else:
                st.error("ë¹„ë°€ë²ˆí˜¸ê°€ ì˜¬ë°”ë¥´ì§€ ì•ŠìŠµë‹ˆë‹¤.")
    return False


with st.sidebar:
    sidebar_brand()
    if GOOGLE_LOGIN_ENABLED and st.user.is_logged_in:
        st.caption(f"ğŸ‘¤ {getattr(st.user, 'email', '')}")
    page = st.radio(
        "ë©”ë‰´",
        ["AI ì¥ì•  ê²€ìƒ‰", "ì¥ì• ì´ë ¥ ê´€ë¦¬", "ìƒˆ ì¥ì•  ë“±ë¡", "ë§¤ë‰´ì–¼ ê´€ë¦¬", "ì‹œìŠ¤í…œ ì •ë³´"],
        key="main_navigation_v2",
        label_visibility="collapsed",
    )
    st.caption("Broadcast Engineering Knowledge System")
    if st.session_state.get("admin_authenticated") and st.button("ê´€ë¦¬ì ë¡œê·¸ì•„ì›ƒ"):
        st.session_state.admin_authenticated = False
        st.rerun()
    if GOOGLE_LOGIN_ENABLED and st.user.is_logged_in:
        st.button("Google ë¡œê·¸ì•„ì›ƒ", on_click=st.logout)

if page in PROTECTED_PAGES and not require_admin_access():
    st.stop()

if page == "AI ì¥ì•  ê²€ìƒ‰":
    st.markdown('<div class="hero"><div class="kicker">AI-powered Broadcast Engineering Knowledge System</div><h1>SPOTV Trouble AI</h1><p class="sub">ê³¼ê±° ì¥ì• ì´ë ¥ì„ ê¸°ë°˜ìœ¼ë¡œ ë°©ì†¡ ì‹œìŠ¤í…œ ë¬¸ì œ í•´ê²°ì„ ì§€ì›í•©ë‹ˆë‹¤.</p></div>', unsafe_allow_html=True)
    total, _, updated = db.stats()
    manual_total, manual_pages, _ = db.manual_stats()
    cols = st.columns(3)
    for col, label, value in zip(cols, ["ë“±ë¡ ì¥ì• ", "ìƒ‰ì¸ ë§¤ë‰´ì–¼", "ìµœê·¼ ì—…ë°ì´íŠ¸"], [total, manual_total, "ì˜¤ëŠ˜" if updated[:10] == datetime.now().strftime("%Y-%m-%d") else updated[:10]]):
        col.markdown(f'<div class="metric"><span>{label}</span><strong>{value}</strong></div>', unsafe_allow_html=True)
    st.write("")
    with st.form("incident_search", border=False):
        query = st.text_input("í˜„ì¥ ì¦ìƒì„ ì…ë ¥í•˜ì„¸ìš”", key="query", placeholder="ì˜ˆ: EVS ì…ë ¥ì´ ì•ˆ ë“¤ì–´ì™€ / vMix ë²„íŠ¼ì´ ë°˜ì‘ ì•ˆ í•¨", label_visibility="collapsed")
        search_submitted = st.form_submit_button("AI ì¥ì•  ë¶„ì„", type="primary")
    if search_submitted:
        if not query.strip():
            st.warning("ì¦ìƒì„ ì…ë ¥í•´ ì£¼ì„¸ìš”.")
        else:
            incidents = db.list_incidents()
            results = semantic_search(query, incidents) if incidents else []
            manual_results = manual_search(query, db.list_manual_chunks())
            if is_ambiguous(query):
                st.markdown('<div class="notice"><b>í˜„ì¬ ì¦ìƒë§Œìœ¼ë¡œëŠ” ë²”ìœ„ê°€ ë„“ìŠµë‹ˆë‹¤.</b><br>ì…ë ¥ ì‹ í˜¸, ì¶œë ¥, ë…¹í™”Â·ì¬ìƒ, ì˜¤ë””ì˜¤ ì¤‘ ì–´ëŠ ë¬¸ì œì¸ì§€ í•¨ê»˜ ì…ë ¥í•˜ë©´ ë” ì •í™•í•˜ê²Œ ì°¾ì„ ìˆ˜ ìˆìŠµë‹ˆë‹¤.</div>', unsafe_allow_html=True)
            top = results[0][1] if results else None
            if results:
                score, top = results[0]
                st.markdown("## ê°€ì¥ ìœ ì‚¬í•œ ê³¼ê±° ì‚¬ë¡€")
                card(top, score, 0)
            analysis, checks = analyze(query, top, [item for _, item in manual_results])
            st.markdown("## AI ë¶„ì„")
            st.write(analysis)
            st.markdown("### ìš°ì„  ì ê²€ ê¶Œì¥ì‚¬í•­")
            for idx, check in enumerate(checks, 1): st.write(f"{idx}. {check}")
            st.markdown(f'<div class="notice"><b>ì£¼ì˜ì‚¬í•­</b><br>{DISCLAIMER}</div>', unsafe_allow_html=True)
            if manual_results:
                st.markdown("## ê´€ë ¨ ì¥ë¹„ ë§¤ë‰´ì–¼")
                for similarity, item in manual_results:
                    manual_card(item, similarity)
            else:
                st.info("ê²€ìƒ‰ ê°€ëŠ¥í•œ ë§¤ë‰´ì–¼ ìƒ‰ì¸ì´ ì—†ìŠµë‹ˆë‹¤. ê´€ë¦¬ìê°€ ë§¤ë‰´ì–¼ ê´€ë¦¬ ë©”ë‰´ì—ì„œ ìƒ‰ì¸í•  ìˆ˜ ìˆìŠµë‹ˆë‹¤.")
            if results:
                st.markdown("## ê´€ë ¨ ê³¼ê±° ì‚¬ë¡€ TOP 3")
                for rank, (similarity, item) in enumerate(results): card(item, similarity, rank)

elif page == "ì¥ì• ì´ë ¥ ê´€ë¦¬":
    st.title("ì¥ì• ì´ë ¥ ê´€ë¦¬")
    st.caption("ë“±ë¡ëœ ì‚¬ê³ ë¥¼ ìˆ˜ì •í•˜ê±°ë‚˜ ì‚­ì œí•  ìˆ˜ ìˆìŠµë‹ˆë‹¤. ìˆ˜ì • ì‹œ ê²€ìƒ‰ ë°ì´í„°ë„ ê°±ì‹ ë©ë‹ˆë‹¤.")
    for item in db.list_incidents():
        with st.expander(f"{item.incident_number} Â· {item.equipment} Â· {item.symptom}"):
            with st.form(f"edit_{item.id}"):
                data = incident_fields(f"edit_{item.id}", item)
                save = st.form_submit_button("ìˆ˜ì • ì €ì¥")
                if save:
                    if not valid(data): st.error("í•„ìˆ˜ í•­ëª©ì„ ëª¨ë‘ ì…ë ¥í•´ ì£¼ì„¸ìš”.")
                    else:
                        try:
                            embedding = create_embedding(" ".join([data["equipment"], data["symptom"], data["cause"], data["action"], data["notes"]]))
                            db.update_incident(item.id, data, embedding)
                            st.success("ì¥ì• ì´ë ¥ì´ ìˆ˜ì •ë˜ì—ˆìŠµë‹ˆë‹¤.")
                            st.rerun()
                        except (sqlite3.IntegrityError, ValueError) as exc: st.error(str(exc) or "ì´ë¯¸ ì‚¬ìš© ì¤‘ì¸ ì‚¬ê³ ë²ˆí˜¸ì…ë‹ˆë‹¤.")
            if st.button("ì‚­ì œ", key=f"delete_{item.id}"):
                db.delete_incident(item.id); st.rerun()

elif page == "ìƒˆ ì¥ì•  ë“±ë¡":
    st.title("ìƒˆ ì¥ì•  ë“±ë¡")
    with st.form("new_incident", clear_on_submit=True):
        data = incident_fields("new")
        submitted = st.form_submit_button("ì¥ì• ì´ë ¥ ë“±ë¡", type="primary")
        if submitted:
            if not valid(data): st.error("í•„ìˆ˜ í•­ëª©ì„ ëª¨ë‘ ì…ë ¥í•´ ì£¼ì„¸ìš”.")
            else:
                try:
                    embedding = create_embedding(" ".join([data["equipment"], data["symptom"], data["cause"], data["action"], data["notes"]]))
                    db.add_incident(data, embedding)
                    st.success("ì¥ì• ì´õß~·¶‰Ëkºwµç]WÙ[X™Y[™Ê^
N‚ˆÛY[HÙ]ÛÜ[˜ZWØÛY[

BˆYˆ›İÛY[‚ˆ™]\›ˆ›Û™BˆN‚ˆ™\ÜÛœÙHHÛY[™[X™Y[™ÜË˜Ü™X]J[Ù[[ÜË™Ù][Š“ÔSRWÑSP‘QS‘×ÓSÑS‹^Y[X™Y[™ËLË\ÛX[ŠK[œ]]^
Bˆ™]\›ˆœÛÛ‹™[\Ê™\ÜÛœÙK™]VÌK™[X™Y[™ÊBˆ^Ù\^Ù\[Û‚ˆ™]\›ˆ›Û™B‚‚™YˆÙ[X[X×ÜÙX\˜Ú
]Y\K[˜ÚY[Ë[Z]LÊN‚ˆÛY[HÙ]ÛÜ[˜ZWØÛY[

BˆYˆÛY[[™[
K™[X™Y[™È›ÜˆH[ˆ[˜ÚY[ÊN‚ˆN‚ˆHHÛY[™[X™Y[™ÜË˜Ü™X]J[Ù[[ÜË™Ù][Š“ÔSRWÑSP‘QS‘×ÓSÑS‹^Y[X™Y[™ËLË\ÛX[ŠK[œ]\]Y\JK™]VÌK™[X™Y[™ÂˆYˆ[œÙWØÛÜÊ˜]ÊN‚ˆˆHœÛÛ‹›ØYÊ˜]ÊBˆ™]\›ˆİ[J
H›ÜˆH[ˆš\
KŠJHÈ
X]œÜ\
İ[J
›Üˆ[ˆJJJ›X]œÜ\
İ[JJH›ÜˆH[ˆŠJJBˆ™]\›ˆÛÜY
Ê[œÙWØÛÜÊK™[X™Y[™ÊKJH›ÜˆH[ˆ[˜ÚY[×KÙ^O[[X™HˆÌK™]™\œÙOUYJVÎ›[Z]Bˆ^Ù\^Ù\[Û‚ˆ\ÜÂˆ™]\›ˆØØ[ÜÙX\˜Ú
]Y\K[˜ÚY[Ë[Z]
B‚‚™YˆX[X[ÜÙX\˜Ú
]Y\KÚ[šÜË[Z]MJN‚ˆˆˆ”ÙX\˜Ú[™^YX[X[\ÜØYÙ\ÈÚ]İ]HZY™XİÜˆ]X˜\ÙKˆˆˆ‚ˆHHØØ[İ™XİÜŠ]Y\JBˆ]Y\Wİ\›\ÈHÂˆ\›H›Üˆ\›H[ˆ™K™š[™[
ˆ–ÌNXK^KVº¬ {g¨ÊËWJÈ‹]Y\K›İÙ\Š
JHYˆ[Š\›JHˆBˆBˆØÛÜ™YH×Bˆ›ÜˆÚ[šÈ[ˆÚ[šÜÎ‚ˆ^\İXÚÈHˆØÚ[šË™Ù]
	İ]IË	ÉÊ_HØÚ[šË™Ù]
	ØÛÛ[	Ë	ÉÊ_H‚ˆØÛÜ™HHÛÜÚ[™JKØØ[İ™XİÜŠ^\İXÚÊJBˆ›Ü›X[^™YÚ^\İXÚÈH^\İXÚË›İÙ\Š
Bˆ^XİÚ]ÈHİ[JH›Üˆ\›H[ˆ]Y\Wİ\›\ÈYˆ\›H[ˆ›Ü›X[^™YÚ^\İXÚÊBˆØÛÜ™H
ÏHZ[ŠŒÍK^XİÚ]È
ˆŒÊBˆYˆØÛÜ™Hˆ‚ˆØÛÜ™Y˜\[™

ØÛÜ™KÚ[šÊJBˆ™]\›ˆÛÜY
ØÛÜ™YÙ^O[[X™H][Nˆ][VÌK™]™\œÙOUYJVÎ›[Z]B‚‚™Yˆ™[]˜[˜ÙWÛX™[
ØÛÜ™K˜[šÊN‚ˆYˆ˜[šÈOH[™ØÛÜ™HHŒÌˆ™]\›ˆºéé;&¬:­ :è*:á¤»'c‚ˆYˆØÛÜ™HHŒMˆ™]\›ˆº­ :è*:á¤»'c‚ˆ™]\›ˆ»,.:¬è:¬ :â©H‚‚‚™Yˆ\×Ø[XšYİ[İ\Ê]Y\JN‚ˆ™]\›ˆ[Š›Ü›X[^™J]Y\JJHHˆÜˆ›İ[JÛÜ™[ˆ]Y\K›İÙ\Š
H›ÜˆÛÜ™[ˆÈ»'¡zè)H‹»-§:è)H‹ºì¡;b¯‹»&):å%;&)‹»!£:é«‹»c¦;'m:ãe‹»fe:êm‹»"è;f.‹»'«; çH‹ºán{fe‹ºîj:¬!—JB