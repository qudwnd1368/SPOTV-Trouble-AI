CSS = r"""
<style>
:root{--bg:#f4f8fc;--panel:#ffffff;--panel2:#eef5fa;--line:#d8e4ec;--text:#142633;--muted:#647b8b;--accent:#087f8c;--accent2:#0b6571;--warn:#a86200}
.stApp{background:radial-gradient(circle at 58% -15%,#e5f6f7 0,#f4f8fc 43%,#eef4f8 100%);color:var(--text)}
[data-testid="stSidebar"]{background:#ffffff;border-right:1px solid var(--line);box-shadow:8px 0 28px rgba(31,65,82,.05)}
[data-testid="stSidebar"] [data-testid="stImage"]{margin:0 auto .7rem}
[data-testid="stSidebar"] [data-testid="stRadio"] label{padding:.62rem .7rem;border-radius:10px;margin:.12rem 0}
[data-testid="stSidebar"] [data-testid="stRadio"] label p{font-size:1.08rem!important;font-weight:650!important;color:#2b4453!important}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked){background:#e8f5f5}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) p{color:var(--accent2)!important;font-weight:800!important}
[data-testid="stHeader"]{background:transparent}.block-container{max-width:1180px;padding-top:3rem}
h1,h2,h3,p,label{font-family:Inter,"Noto Sans KR",sans-serif;color:var(--text)}.hero{text-align:center;padding:2.8rem 0 1.4rem}
.hero h1{font-size:3.25rem;margin:0;letter-spacing:-.04em;color:#102f3b}.kicker{color:var(--accent);font-size:.82rem;letter-spacing:.16em;text-transform:uppercase;font-weight:800}
.sub{color:var(--muted);font-size:1.03rem}.metric,.card,.notice,.lock-card{background:rgba(255,255,255,.94);border:1px solid var(--line);border-radius:18px;padding:1.15rem 1.3rem;box-shadow:0 12px 38px rgba(30,67,84,.08)}
.metric span{color:var(--muted);font-size:.8rem}.metric strong{display:block;color:#163a48;font-size:1.65rem;margin-top:.2rem}.badge{display:inline-block;color:var(--accent2);background:#e5f5f4;border:1px solid #b7dfdc;padding:.22rem .55rem;border-radius:999px;font-size:.76rem;font-weight:800}
.card{margin:.7rem 0}.card h3{margin:.65rem 0}.label{color:var(--muted);font-size:.76rem;text-transform:uppercase;letter-spacing:.06em}.value{margin:.15rem 0 .8rem;color:var(--text)}.notice{border-color:#edcf9d;background:#fffaf1;color:#855012}.notice b{color:#6e4008}
.manual-card .value{line-height:1.65}.manual-source{color:var(--muted);font-size:.82rem}.manual-source a{color:var(--accent2);font-weight:750;text-decoration:none}
.lock-card{text-align:center;max-width:570px;margin:4.5rem auto 1.3rem}.lock-icon{font-size:2.2rem}.lock-card h2{margin:.5rem 0}.lock-card p{color:var(--muted)}
.stTextInput input,.stTextArea textarea{background:#fff!important;border:1px solid #cbdbe5!important;color:#17313e!important;border-radius:12px!important;box-shadow:0 2px 8px rgba(30,67,84,.03)}
.stTextInput input{min-height:3.4rem;font-size:1.05rem}.stButton>button{border-radius:11px;border:1px solid #b6d1d8;background:#eef7f8;color:#175562;width:100%;font-weight:750}.stButton>button:hover{border-color:var(--accent);color:var(--accent2);background:#e3f3f3}
.stButton>button[kind="primary"]{background:var(--accent);border-color:var(--accent);color:#fff}.stButton>button[kind="primary"]:hover{background:var(--accent2);color:#fff}
div[data-testid="stForm"]{background:rgba(255,255,255,.86);border:1px solid var(--line);border-radius:18px;padding:1.25rem}
[data-testid="stExpander"]{background:#fff;border-color:var(--line)!important;border-radius:13px!important}
</style>
"""
