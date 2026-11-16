#!/usr/bin/env python3
"""
새벽부대 인트라넷 - 가상의 부대 인트라넷 데모 (훈련·실습용, 실제 군 기관과 무관)
=====================================================
표준 라이브러리만 사용합니다. 설치할 것이 없습니다.

    python app.py            ->  http://127.0.0.1:8000
    PORT=9000 python app.py  ->  포트 변경
    HOST=0.0.0.0 python app.py -> 같은 네트워크의 다른 기기에서 접속 허용

데모 계정
    관리자  admin / admin1234
    일반    jykim / nova1234   (다른 직원 계정도 비밀번호 동일)

DB 초기화: 같은 폴더의 intranet.db 파일을 지우고 다시 실행하세요.
"""
import calendar
import datetime as dt
import hashlib
import hmac
import html
import os
import re
import secrets
import sqlite3
import threading
import time
import traceback
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "intranet.db")
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))

COMPANY = "새벽부대"
SESSION_HOURS = 8
MAX_BODY = 200_000          # POST 본문 최대 크기(바이트)
PBKDF2_ITER = 200_000
LOGIN_MAX_FAILS = 5         # 연속 실패 허용 횟수
LOGIN_LOCK_SECONDS = 300    # 초과 시 잠금 시간
PAGE_SIZE = 10

CATEGORIES = ["자유", "질문", "교육자료", "경조사"]
APPROVAL_KINDS = ["휴가", "외출·외박", "물자청구", "출장"]
STATUS_LABEL = {"pending": "대기", "approved": "승인", "rejected": "반려"}
MESSAGES = {
    "saved": "저장되었습니다.",
    "deleted": "삭제되었습니다.",
    "posted": "등록되었습니다.",
    "decided": "결재가 처리되었습니다.",
    "pw": "비밀번호가 변경되었습니다. 다른 기기의 로그인은 모두 해제되었습니다.",
    "bye": "로그아웃되었습니다.",
}


# ───────────────────────── 유틸 ─────────────────────────
def e(value):
    """HTML 이스케이프. 화면에 나가는 모든 사용자 입력은 이 함수를 거칩니다."""
    return html.escape("" if value is None else str(value), quote=True)


def nl2br(value):
    return e(value).replace("\n", "<br>")


def now_str():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def hash_pw(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITER)
    return salt.hex() + "$" + digest.hex()


def check_pw(password, stored):
    try:
        salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), PBKDF2_ITER)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except ValueError:
        return False


DUMMY_HASH = hash_pw(secrets.token_hex(8))  # 없는 계정도 같은 시간이 걸리도록


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def like(term):
    esc = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return "%" + esc + "%"


def to_int(value, default=1):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ───────────────────────── 로그인 시도 제한 ─────────────────────────
_fails = {}
_fails_lock = threading.Lock()


def login_locked(key):
    with _fails_lock:
        count, until = _fails.get(key, (0, 0))
        if until > time.time():
            return int(until - time.time())
        if until and until <= time.time():
            _fails.pop(key, None)
        return 0


def login_failed(key):
    with _fails_lock:
        count, _ = _fails.get(key, (0, 0))
        count += 1
        until = time.time() + LOGIN_LOCK_SECONDS if count >= LOGIN_MAX_FAILS else 0
        _fails[key] = (count, until)


def login_ok(key):
    with _fails_lock:
        _fails.pop(key, None)


# ───────────────────────── DB ─────────────────────────
SCHEMA = """
CREATE TABLE users(
  id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, pw TEXT NOT NULL,
  name TEXT NOT NULL, dept TEXT NOT NULL, title TEXT NOT NULL,
  email TEXT, phone TEXT, ext TEXT, role TEXT NOT NULL DEFAULT 'user', joined TEXT);
CREATE TABLE sessions(
  token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, csrf TEXT NOT NULL, expires REAL NOT NULL);
CREATE TABLE notices(
  id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL,
  author_id INTEGER NOT NULL, pinned INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL);
CREATE TABLE posts(
  id INTEGER PRIMARY KEY, category TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
  author_id INTEGER NOT NULL, views INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL);
CREATE TABLE comments(
  id INTEGER PRIMARY KEY, post_id INTEGER NOT NULL, author_id INTEGER NOT NULL,
  body TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE approvals(
  id INTEGER PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
  drafter_id INTEGER NOT NULL, approver_id INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending', comment TEXT, created TEXT NOT NULL, decided TEXT);
CREATE TABLE events(
  id INTEGER PRIMARY KEY, title TEXT NOT NULL, date TEXT NOT NULL, time TEXT, place TEXT,
  owner_id INTEGER NOT NULL, scope TEXT NOT NULL DEFAULT 'personal');
"""


def connect():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def init_db():
    if os.path.exists(DB_PATH):
        return
    print("처음 실행: 데모 데이터를 만드는 중...")
    db = connect()
    db.executescript(SCHEMA)
    people = [
        ("admin", "한서윤", "인사과", "소령", "admin", "2024-12-02"),
        ("jykim", "김지윤", "통신소대", "병장", "user", "2025-06-16"),
        ("mspark", "박민수", "통신소대", "중위", "user", "2025-07-01"),
        ("jhlim", "임재현", "작전과", "상사", "user", "2023-03-06"),
        ("sylee", "이서연", "정보과", "대위", "user", "2025-01-13"),
        ("sahan", "한수아", "정보과", "일병", "user", "2026-08-24"),
        ("dhchoi", "최도현", "작전과", "소령", "user", "2024-06-10"),
        ("twoh", "오태원", "군수과", "중사", "user", "2022-11-21"),
        ("yjjung", "정유진", "인사과", "중사", "user", "2023-09-04"),
        ("hwkang", "강현우", "군수과", "대위", "user", "2025-12-15"),
        ("eyoon", "윤은지", "본부중대", "상병", "user", "2026-01-19"),
        ("nrshin", "신나래", "본부중대", "하사", "user", "2024-04-08"),
    ]
    for i, (un, name, dept, title, role, joined) in enumerate(people, 1):
        pw = hash_pw("admin1234" if role == "admin" else "nova1234")
        db.execute(
            "INSERT INTO users(username,pw,name,dept,title,email,phone,ext,role,joined) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (un, pw, name, dept, title, f"{un}@saebyeok.example",
             f"010-55{i:02d}-{1000 + i * 137:04d}", f"9{200 + i}", role, joined))

    today = dt.date.today()

    def ago(days, hm="09:30"):
        return f"{today - dt.timedelta(days=days)} {hm}"

    notices = [
        ("[필독] 하반기 보안 교육 이수 안내", "전 부대원은 이번 달 말까지 하반기 보안 교육을 이수하기 바랍니다.\n\n- 대상: 전 부대원\n- 방법: 사이버지식정보방 또는 처부 PC에서 온라인 수강\n- 소요 시간: 약 40분\n\n미이수자는 다음 달 인트라넷 계정 사용이 일부 제한될 수 있습니다.", 5, 1, ago(1)),
        ("동계 대비 난방 시설 점검 안내", "이번 주 토요일 09:00~15:00 생활관 난방 시설 점검을 실시합니다.\n점검 시간에는 생활관 출입이 일부 통제됩니다.", 8, 0, ago(2, "14:10")),
        ("연말 휴가 계획 제출 안내", "12월 휴가 계획은 다음 주 금요일까지 인사과로 제출하기 바랍니다.\n양식은 게시판 '교육자료'에 올려 두었습니다.", 9, 0, ago(4, "11:00")),
        ("전입 신병 소개 (정보과 한수아 일병)", "정보과에 한수아 일병이 전입했습니다. 따뜻하게 맞아 주기 바랍니다.", 9, 0, ago(6, "10:05")),
        ("인트라넷 정기 점검 안내", "수요일 22:00~23:00 인트라넷 서버 점검이 예정되어 있습니다.\n해당 시간에는 접속이 끊길 수 있습니다.", 3, 0, ago(9, "17:40")),
    ]
    db.executemany("INSERT INTO notices(title,body,author_id,pinned,created) VALUES(?,?,?,?,?)", notices)

    posts = [
        ("자유", "이번 주 PX 신상 들어왔습니다", "냉동 코너에 새로 들어온 것 있으니 참고하세요. 금방 빠질 것 같습니다.", 11, 34, ago(0, "11:20")),
        ("질문", "사이버지식정보방 PC 로그인이 안 됩니다", "3번 자리 PC가 계속 로그인 화면에서 멈춥니다. 저만 그런가요?", 4, 58, ago(1, "16:02")),
        ("교육자료", "비밀번호 관리 수칙 정리", "통신소대에서 정리한 계정 관리 수칙입니다.\n\n1. 비밀번호는 8자 이상, 영문과 숫자를 섞어 쓴다\n2. 계정을 다른 사람과 같이 쓰지 않는다\n3. 자리를 비울 때는 화면을 잠근다\n4. 비밀번호를 메모지에 적어 붙여 두지 않는다", 3, 121, ago(2, "09:48")),
        ("경조사", "군수과 강현우 대위 득녀 소식", "축하드립니다! 산모와 아기 모두 건강하다고 합니다.", 9, 87, ago(3, "13:15")),
        ("자유", "부대 풋살 동아리 인원 모집", "매주 목요일 일과 후, 연병장 옆 풋살장입니다. 초보 환영!", 8, 45, ago(5, "18:30")),
        ("교육자료", "휴가 계획 제출 양식 모음", "인사과에서 안내한 양식 목록입니다. 제출 전에 미리 확인하기 바랍니다.", 12, 203, ago(4, "11:30")),
        ("질문", "면회 신청은 어디서 합니까?", "전입 온 지 얼마 안 돼서 질문드립니다. 결재 메뉴에서 올리면 됩니까?", 6, 29, ago(6, "10:40")),
        ("자유", "체력단련실 러닝머신 수리 완료", "2번 러닝머신 고쳐졌습니다. 이제 정상 사용 가능합니다.", 5, 61, ago(7, "15:22")),
        ("교육자료", "수상한 메일 구별법 정리", "정보과에서 정리한 내용입니다.\n\n- 발신 주소를 끝까지 확인\n- 급하게 클릭을 유도하는 문구 주의\n- 첨부 파일의 확장자 확인\n- 의심되면 정보과(군 전화 9205)로 신고", 7, 176, ago(8, "09:10")),
        ("자유", "다음 달 체육대회 종목 투표", "족구 vs 풋살, 댓글로 의견 남겨 주세요.", 1, 142, ago(10, "14:00")),
        ("질문", "보급품을 분실했을 때 처리 절차", "방한 장갑 한 짝을 잃어버렸는데 어떻게 처리하면 됩니까?", 11, 38, ago(11, "17:05")),
        ("자유", "주말 종교 활동 차량 시간 변경", "일요일 차량 출발이 09:00에서 09:30으로 바뀌었습니다.", 2, 22, ago(12, "18:45")),
    ]
    db.executemany("INSERT INTO posts(category,title,body,author_id,views,created) VALUES(?,?,?,?,?,?)", posts)
    comments = [
        (1, 2, "정보 감사합니다. 일과 끝나고 가 봐야겠습니다.", ago(0, "11:41")),
        (1, 5, "어제 벌써 절반은 나갔더군요.", ago(0, "12:03")),
        (2, 3, "통신소대에서 확인했습니다. 오늘 중으로 조치하겠습니다.", ago(1, "16:30")),
        (3, 2, "잘 참고하겠습니다. 감사합니다!", ago(2, "10:15")),
        (7, 1, "결재 메뉴에서 '외출·외박' 문서로 올리면 됩니다. 자세한 것은 인사과로 문의하세요.", ago(6, "11:02")),
        (10, 6, "풋살에 한 표입니다!", ago(10, "14:20")),
        (10, 4, "족구가 인원 맞추기 편할 것 같습니다.", ago(10, "15:01")),
    ]
    db.executemany("INSERT INTO comments(post_id,author_id,body,created) VALUES(?,?,?,?)", comments)

    approvals = [
        ("휴가", "정기휴가 신청 (4박 5일)", f"기간: {today + dt.timedelta(days=4)} ~ {today + dt.timedelta(days=8)}\n행선지: 대구\n사유: 정기휴가", 2, 3, "pending", None, ago(0, "10:12"), None),
        ("물자청구", "통신 케이블 및 커넥터 청구", "품목: 랜 케이블 100m, 커넥터 50개\n사유: 생활관 사이버지식정보방 배선 교체", 2, 1, "pending", None, ago(1, "15:40"), None),
        ("외출·외박", "주말 외박 신청", "기간: 토요일 08:00 ~ 일요일 20:00\n사유: 가족 면회", 11, 1, "pending", None, ago(1, "09:05"), None),
        ("물자청구", "동계 피복 추가 청구", "품목: 방한 장갑 20켤레\n사유: 전입 인원 증가", 8, 1, "pending", None, ago(2, "13:25"), None),
        ("외출·외박", "평일 외출 신청", "시간: 14:00 ~ 18:00\n사유: 개인 용무", 2, 3, "approved", "확인했습니다.", ago(8, "09:00"), ago(8, "09:40")),
        ("출장", "보안 교육 과정 입교", "기간: 2박 3일\n목적: 보안 담당자 교육 참석", 5, 1, "approved", "승인합니다.", ago(6, "11:10"), ago(5, "10:00")),
        ("물자청구", "체력단련실 기구 교체 요청", "품목: 벤치 프레스 1대\n사유: 노후", 4, 1, "rejected", "예산 사정상 다음 분기에 재검토하겠습니다.", ago(7, "16:20"), ago(6, "09:30")),
    ]
    db.executemany(
        "INSERT INTO approvals(kind,title,body,drafter_id,approver_id,status,comment,created,decided) VALUES(?,?,?,?,?,?,?,?,?)",
        approvals)

    def day(offset):
        return str(today + dt.timedelta(days=offset))

    events = [
        ("주간 회의", day(0), "10:00", "회의실", 1, "company"),
        ("보안 교육 이수 마감", day(9), "", "온라인", 1, "company"),
        ("체력 검정", day(3), "14:00", "연병장", 1, "company"),
        ("장비 점검의 날", day(12), "09:00", "", 1, "company"),
        ("부대 창설 기념일", day(18), "", "", 1, "company"),
        ("통신 장비 점검", day(1), "15:00", "통신실", 2, "personal"),
        ("면회", day(5), "13:00", "면회실", 2, "personal"),
        ("월간 정비의 날", day(-3), "", "", 1, "company"),
    ]
    db.executemany("INSERT INTO events(title,date,time,place,owner_id,scope) VALUES(?,?,?,?,?,?)", events)
    db.commit()
    db.close()


# ───────────────────────── 화면 조각 ─────────────────────────
ICONS = {
    "home": "M3 11l9-8 9 8M5 10v10h14V10",
    "notices": "M4 5h16v11H8l-4 4z",
    "board": "M5 4h14v16H5zM9 9h6M9 13h6",
    "approvals": "M9 12l2 2 4-4M5 4h14v16H5z",
    "calendar": "M4 6h16v14H4zM4 10h16M8 3v4M16 3v4",
    "people": "M8 11a3 3 0 100-6 3 3 0 000 6zM2 20c0-3 3-5 6-5s6 2 6 5M17 11a3 3 0 100-6M18 15c2 .5 4 2 4 5",
}
NAV = [("home", "/", "홈"), ("notices", "/notices", "공지사항"), ("board", "/board", "게시판"),
       ("approvals", "/approvals", "결재"), ("calendar", "/calendar", "일정"), ("people", "/people", "부대원")]


def icon(name):
    return (f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round"><path d="{ICONS[name]}"/></svg>')


def avatar(user_id, name, size=""):
    return f'<span class="av c{user_id % 6} {size}">{e(name[:1])}</span>'


def badge(status):
    return f'<span class="badge {e(status)}">{STATUS_LABEL.get(status, e(status))}</span>'


def empty(text):
    return f'<p class="empty">{e(text)}</p>'


def pager(page, total, path, params):
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    if pages <= 1:
        return ""
    out = ['<nav class="pager">']
    for p in range(1, pages + 1):
        qs = urlencode({**{k: v for k, v in params.items() if v}, "page": p})
        cls = ' class="on"' if p == page else ""
        out.append(f'<a{cls} href="{e(path)}?{e(qs)}">{p}</a>')
    out.append("</nav>")
    return "".join(out)


def shell(title, inner):
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} · {COMPANY} 인트라넷</title>
<link rel="stylesheet" href="/static/app.css"></head>
<body><div class="classbar">훈련용 가상 시스템 · 실제 군 기관과 무관 · 평문</div>{inner}</body></html>"""


# ───────────────────────── 라우터 ─────────────────────────
ROUTES = []


def route(method, pattern, login=True, admin=False):
    def deco(fn):
        ROUTES.append((method, re.compile(pattern), fn, login, admin))
        return fn
    return deco


class Handler(BaseHTTPRequestHandler):
    server_version = "Intranet"
    sys_version = ""

    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} {fmt % args}")

    # ── 응답 헬퍼 ──
    def send(self, code, body, ctype="text/html; charset=utf-8", extra=None):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'none'; frame-ancestors 'none'; form-action 'self'")
        if not ctype.startswith("text/css"):
            self.send_header("Cache-Control", "no-store")
        for k, v in (extra or []):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location, extra=None):
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        for k, v in (extra or []):
            self.send_header(k, v)
        self.end_headers()

    def fail(self, code, text):
        inner = (f'<main class="lone"><div class="card center"><p class="code">{code}</p>'
                 f'<h1>{e(text)}</h1><a class="btn" href="/">홈으로</a></div></main>')
        self.send(code, shell(text, inner))

    def page(self, title, active, body, actions=""):
        u = self.user
        pending = self.db.execute(
            "SELECT COUNT(*) FROM approvals WHERE approver_id=? AND status='pending'", (u["id"],)).fetchone()[0]
        links = []
        for key, href, label in NAV:
            cnt = f'<b class="cnt">{pending}</b>' if key == "approvals" and pending else ""
            on = " on" if key == active else ""
            links.append(f'<a class="nav{on}" href="{href}">{icon(key)}<span>{label}</span>{cnt}</a>')
        msg = MESSAGES.get(self.q.get("m", ""))
        flash = f'<div class="flash">{e(msg)}</div>' if msg else ""
        inner = f"""
<div class="app">
  <aside class="side">
    <a class="brand" href="/"><i>★</i><span>{COMPANY}<small>인트라넷</small></span></a>
    <nav>{''.join(links)}</nav>
    <a class="me" href="/me">{avatar(u['id'], u['name'])}
      <span><b>{e(u['title'])} {e(u['name'])}</b><small>{e(u['dept'])}</small></span></a>
  </aside>
  <div class="main">
    <header class="top">
      <h1>{e(title)}</h1>
      <div class="top-r">{actions}
        <form method="post" action="/logout"><input type="hidden" name="csrf" value="{e(self.sess['csrf'])}">
        <button class="btn ghost">로그아웃</button></form></div>
    </header>
    {flash}
    <div class="content">{body}</div>
  </div>
</div>"""
        self.send(200, shell(title, inner))

    def csrf(self):
        return f'<input type="hidden" name="csrf" value="{e(self.sess["csrf"])}">'

    @property
    def is_admin(self):
        return self.user["role"] == "admin"

    # ── 요청 처리 ──
    def load_session(self):
        jar = cookies.SimpleCookie()
        try:
            jar.load(self.headers.get("Cookie", ""))
        except cookies.CookieError:
            return None, None
        if "sid" not in jar:
            return None, None
        sess = self.db.execute("SELECT * FROM sessions WHERE token=? AND expires>?",
                               (token_hash(jar["sid"].value), time.time())).fetchone()
        if not sess:
            return None, None
        user = self.db.execute("SELECT * FROM users WHERE id=?", (sess["user_id"],)).fetchone()
        return (user, sess) if user else (None, None)

    def dispatch(self, method):
        parsed = urlparse(self.path)
        path = parsed.path
        self.q = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        self.form = {}
        if path == "/static/app.css" and method == "GET":
            return self.send(200, CSS, "text/css; charset=utf-8", [("Cache-Control", "max-age=300")])
        self.db = connect()
        try:
            if method == "POST":
                length = to_int(self.headers.get("Content-Length"), 0)
                if length < 0 or length > MAX_BODY:
                    return self.fail(413, "요청이 너무 큽니다")
                raw = self.rfile.read(length).decode("utf-8", "replace")
                self.form = {k: v[0].strip() for k, v in parse_qs(raw, keep_blank_values=True).items()}
            self.user, self.sess = self.load_session()
            for m, rx, fn, need_login, need_admin in ROUTES:
                match = rx.fullmatch(path)
                if m != method or not match:
                    continue
                if need_login:
                    if not self.user:
                        return self.redirect("/login")
                    if method == "POST" and not hmac.compare_digest(self.form.get("csrf", ""), self.sess["csrf"]):
                        return self.fail(403, "요청을 확인할 수 없습니다 (CSRF)")
                    if need_admin and not self.is_admin:
                        return self.fail(403, "권한이 없습니다")
                return fn(self, *[int(g) for g in match.groups()])
            if not self.user:
                return self.redirect("/login")
            self.fail(404, "페이지를 찾을 수 없습니다")
        except Exception:
            traceback.print_exc()
            try:
                self.fail(500, "서버 오류가 발생했습니다")
            except Exception:
                pass
        finally:
            self.db.close()


# ───────────────────────── 로그인 ─────────────────────────
def login_page(h, error="", username=""):
    err = f'<p class="err">{e(error)}</p>' if error else ""
    msg = MESSAGES.get(h.q.get("m", ""))
    info = f'<p class="info">{e(msg)}</p>' if msg and not error else ""
    inner = f"""
<main class="login">
  <section class="login-art">
    <a class="brand big"><i>★</i><span>{COMPANY}<small>인트라넷</small></span></a>
    <h2>부대 업무를<br>한 곳에서.</h2>
    <p>공지 · 게시판 · 결재 · 일정 · 부대원 검색</p>
  </section>
  <section class="login-form">
    <form method="post" action="/login" class="card">
      <h1>로그인</h1>{err}{info}
      <label>아이디<input name="username" value="{e(username)}" autocomplete="username" required autofocus></label>
      <label>비밀번호<input name="password" type="password" autocomplete="current-password" required></label>
      <button class="btn primary wide">로그인</button>
      <div class="hint"><b>데모 계정</b><br>관리자 <code>admin</code> / <code>admin1234</code><br>
      일반 <code>jykim</code> / <code>nova1234</code></div>
    </form>
  </section>
</main>"""
    h.send(200 if not error else 401, shell("로그인", inner))


@route("GET", r"/login", login=False)
def login_get(h):
    if h.user:
        return h.redirect("/")
    login_page(h)


@route("POST", r"/login", login=False)
def login_post(h):
    username = h.form.get("username", "")[:40]
    password = h.form.get("password", "")[:200]
    key = (h.client_address[0], username.lower())
    wait = login_locked(key)
    if wait:
        return login_page(h, f"로그인 시도가 너무 많습니다. {wait // 60 + 1}분 뒤에 다시 시도해 주세요.", username)
    user = h.db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    valid = check_pw(password, user["pw"] if user else DUMMY_HASH)
    if not user or not valid:
        login_failed(key)
        return login_page(h, "아이디 또는 비밀번호가 올바르지 않습니다.", username)
    login_ok(key)
    token = secrets.token_urlsafe(32)
    h.db.execute("DELETE FROM sessions WHERE expires<?", (time.time(),))
    h.db.execute("INSERT INTO sessions(token,user_id,csrf,expires) VALUES(?,?,?,?)",
                 (token_hash(token), user["id"], secrets.token_urlsafe(24), time.time() + SESSION_HOURS * 3600))
    h.db.commit()
    cookie = f"sid={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age={SESSION_HOURS * 3600}"
    h.redirect("/", [("Set-Cookie", cookie)])


@route("POST", r"/logout")
def logout(h):
    h.db.execute("DELETE FROM sessions WHERE token=?", (h.sess["token"],))
    h.db.commit()
    h.redirect("/login?m=bye", [("Set-Cookie", "sid=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0")])


# ───────────────────────── 홈 ─────────────────────────
@route("GET", r"/")
def home(h):
    u, db = h.user, h.db
    today = dt.date.today()
    week_ago = str(today - dt.timedelta(days=7))
    inbox = db.execute("SELECT COUNT(*) FROM approvals WHERE approver_id=? AND status='pending'", (u["id"],)).fetchone()[0]
    mine = db.execute("SELECT COUNT(*) FROM approvals WHERE drafter_id=? AND status='pending'", (u["id"],)).fetchone()[0]
    ev_today = db.execute("SELECT COUNT(*) FROM events WHERE date=? AND (scope='company' OR owner_id=?)",
                          (str(today), u["id"])).fetchone()[0]
    new_notice = db.execute("SELECT COUNT(*) FROM notices WHERE created>=?", (week_ago,)).fetchone()[0]
    stats = [("결재 대기", inbox, "/approvals"), ("내 기안 진행 중", mine, "/approvals?tab=sent"),
             ("오늘 일정", ev_today, "/calendar"), ("이번 주 새 공지", new_notice, "/notices")]
    cards = "".join(f'<a class="stat" href="{href}"><small>{label}</small><b>{n}</b></a>' for label, n, href in stats)

    notices = db.execute("SELECT id,title,pinned,created FROM notices ORDER BY pinned DESC, created DESC LIMIT 5").fetchall()
    n_html = "".join(
        f'<li><a href="/notices/{r["id"]}">{"<span class=pin>고정</span>" if r["pinned"] else ""}{e(r["title"])}</a>'
        f'<time>{e(r["created"][5:10])}</time></li>' for r in notices) or empty("공지가 없습니다.")

    todo = db.execute("""SELECT a.id,a.kind,a.title,a.created,u.name,u.id uid FROM approvals a
                         JOIN users u ON u.id=a.drafter_id
                         WHERE a.approver_id=? AND a.status='pending' ORDER BY a.created DESC LIMIT 5""", (u["id"],)).fetchall()
    t_html = "".join(
        f'<li><a href="/approvals/{r["id"]}"><span class="tag">{e(r["kind"])}</span>{e(r["title"])}</a>'
        f'<time>{e(r["name"])}</time></li>' for r in todo)
    t_html = f"<ul class='list'>{t_html}</ul>" if t_html else empty("결재할 문서가 없습니다.")

    events = db.execute("""SELECT * FROM events WHERE date>=? AND (scope='company' OR owner_id=?)
                           ORDER BY date, time LIMIT 5""", (str(today), u["id"])).fetchall()
    ev_html = "".join(
        f'<li><span class="date"><b>{e(r["date"][8:10])}</b>{e(r["date"][5:7])}월</span>'
        f'<span class="grow">{e(r["title"])}<small>{e(r["time"] or "종일")}{" · " + e(r["place"]) if r["place"] else ""}'
        f'{"" if r["scope"] == "company" else " · 개인"}</small></span></li>' for r in events)
    ev_html = f"<ul class='agenda'>{ev_html}</ul>" if ev_html else empty("예정된 일정이 없습니다.")

    posts = db.execute("""SELECT p.id,p.title,p.category,p.created,
                          (SELECT COUNT(*) FROM comments c WHERE c.post_id=p.id) cc
                          FROM posts p ORDER BY p.created DESC LIMIT 5""").fetchall()
    p_html = "".join(
        f'<li><a href="/board/{r["id"]}"><span class="tag">{e(r["category"])}</span>{e(r["title"])}'
        f'{" <em>[" + str(r["cc"]) + "]</em>" if r["cc"] else ""}</a><time>{e(r["created"][5:10])}</time></li>' for r in posts)

    weekday = "월화수목금토일"[today.weekday()]
    body = f"""
<section class="hero"><div><h2>{e(u['title'])} {e(u['name'])} 님, 환영합니다</h2>
<p>{today.year}년 {today.month}월 {today.day}일 {weekday}요일 · {e(u['dept'])}</p></div>
<a class="btn primary" href="/approvals/new">기안 작성</a></section>
<section class="stats">{cards}</section>
<section class="grid2">
  <div class="card"><h3>공지사항 <a href="/notices">전체 보기</a></h3><ul class="list">{n_html}</ul></div>
  <div class="card"><h3>결재 대기함 <a href="/approvals">전체 보기</a></h3>{t_html}</div>
  <div class="card"><h3>다가오는 일정 <a href="/calendar">달력 보기</a></h3>{ev_html}</div>
  <div class="card"><h3>최근 게시글 <a href="/board">전체 보기</a></h3><ul class="list">{p_html}</ul></div>
</section>"""
    h.page("홈", "home", body)


# ───────────────────────── 공지사항 ─────────────────────────
@route("GET", r"/notices")
def notices(h):
    rows = h.db.execute("""SELECT n.*, u.name FROM notices n JOIN users u ON u.id=n.author_id
                           ORDER BY n.pinned DESC, n.created DESC""").fetchall()
    trs = "".join(
        f'<tr><td class="num">{"<span class=pin>고정</span>" if r["pinned"] else r["id"]}</td>'
        f'<td><a href="/notices/{r["id"]}">{e(r["title"])}</a></td>'
        f'<td>{e(r["name"])}</td><td class="dim">{e(r["created"][:10])}</td></tr>' for r in rows)
    actions = '<a class="btn primary" href="/notices/new">공지 작성</a>' if h.is_admin else ""
    body = (f'<div class="card flush"><table><thead><tr><th class="num">번호</th><th>제목</th><th>작성자</th>'
            f'<th>등록일</th></tr></thead><tbody>{trs}</tbody></table></div>') if rows else empty("공지가 없습니다.")
    h.page("공지사항", "notices", body, actions)


@route("GET", r"/notices/new", admin=True)
def notice_new(h, error=""):
    err = f'<p class="err">{e(error)}</p>' if error else ""
    body = f"""<form method="post" class="card form">{h.csrf()}{err}
<label>제목<input name="title" maxlength="120" value="{e(h.form.get('title', ''))}" required></label>
<label>내용<textarea name="body" rows="12" maxlength="5000" required>{e(h.form.get('body', ''))}</textarea></label>
<label class="check"><input type="checkbox" name="pinned" value="1"> 상단에 고정</label>
<div class="row"><a class="btn" href="/notices">취소</a><button class="btn primary">등록</button></div></form>"""
    h.page("공지 작성", "notices", body)


@route("POST", r"/notices/new", admin=True)
def notice_create(h):
    title, text = h.form.get("title", "")[:120], h.form.get("body", "")[:5000]
    if not title or not text:
        return notice_new(h, "제목과 내용을 모두 입력해 주세요.")
    cur = h.db.execute("INSERT INTO notices(title,body,author_id,pinned,created) VALUES(?,?,?,?,?)",
                       (title, text, h.user["id"], 1 if h.form.get("pinned") else 0, now_str()))
    h.db.commit()
    h.redirect(f"/notices/{cur.lastrowid}?m=posted")


@route("GET", r"/notices/(\d+)")
def notice_view(h, nid):
    r = h.db.execute("""SELECT n.*, u.name, u.dept, u.id uid FROM notices n JOIN users u ON u.id=n.author_id
                        WHERE n.id=?""", (nid,)).fetchone()
    if not r:
        return h.fail(404, "공지를 찾을 수 없습니다")
    delete = (f'<form method="post" action="/notices/{nid}/delete">{h.csrf()}<button class="btn danger">삭제</button></form>'
              if h.is_admin else "")
    body = f"""<article class="card doc">
<h2>{"<span class=pin>고정</span>" if r["pinned"] else ""}{e(r['title'])}</h2>
<div class="meta">{avatar(r['uid'], r['name'], 'sm')}<span>{e(r['name'])} · {e(r['dept'])}</span><time>{e(r['created'])}</time></div>
<div class="text">{nl2br(r['body'])}</div></article>
<div class="row"><a class="btn" href="/notices">목록</a>{delete}</div>"""
    h.page("공지사항", "notices", body)


@route("POST", r"/notices/(\d+)/delete", admin=True)
def notice_delete(h, nid):
    h.db.execute("DELETE FROM notices WHERE id=?", (nid,))
    h.db.commit()
    h.redirect("/notices?m=deleted")


# ───────────────────────── 게시판 ─────────────────────────
@route("GET", r"/board")
def board(h):
    cat = h.q.get("cat", "") if h.q.get("cat") in CATEGORIES else ""
    term = h.q.get("q", "").strip()[:50]
    page = max(1, to_int(h.q.get("page")))
    where, args = [], []
    if cat:
        where.append("p.category=?")
        args.append(cat)
    if term:
        where.append("(p.title LIKE ? ESCAPE '\\' OR p.body LIKE ? ESCAPE '\\')")
        args += [like(term), like(term)]
    clause = "WHERE " + " AND ".join(where) if where else ""
    total = h.db.execute(f"SELECT COUNT(*) FROM posts p {clause}", args).fetchone()[0]
    rows = h.db.execute(f"""SELECT p.*, u.name, (SELECT COUNT(*) FROM comments c WHERE c.post_id=p.id) cc
                            FROM posts p JOIN users u ON u.id=p.author_id {clause}
                            ORDER BY p.created DESC LIMIT ? OFFSET ?""",
                        args + [PAGE_SIZE, (page - 1) * PAGE_SIZE]).fetchall()
    tabs = "".join(
        f'<a class="{"on" if c == cat else ""}" href="/board?{e(urlencode({k: v for k, v in (("cat", c), ("q", term)) if v}))}">'
        f'{e(c or "전체")}</a>' for c in [""] + CATEGORIES)
    trs = "".join(
        f'<tr><td><span class="tag">{e(r["category"])}</span></td>'
        f'<td><a href="/board/{r["id"]}">{e(r["title"])}</a>{" <em>[" + str(r["cc"]) + "]</em>" if r["cc"] else ""}</td>'
        f'<td>{e(r["name"])}</td><td class="dim">{e(r["created"][:10])}</td><td class="num dim">{r["views"]}</td></tr>'
        for r in rows)
    table = (f'<div class="card flush"><table><thead><tr><th>분류</th><th>제목</th><th>작성자</th><th>등록일</th>'
             f'<th class="num">조회</th></tr></thead><tbody>{trs}</tbody></table></div>') if rows else empty("게시글이 없습니다.")
    body = f"""<div class="toolbar"><nav class="tabs">{tabs}</nav>
<form class="search" method="get" action="/board"><input type="hidden" name="cat" value="{e(cat)}">
<input name="q" value="{e(term)}" placeholder="제목·내용 검색" maxlength="50"><button class="btn">검색</button></form></div>
{table}{pager(page, total, "/board", {"cat": cat, "q": term})}"""
    h.page("게시판", "board", body, '<a class="btn primary" href="/board/new">글쓰기</a>')


@route("GET", r"/board/new")
def post_new(h, error=""):
    err = f'<p class="err">{e(error)}</p>' if error else ""
    opts = "".join(f'<option{" selected" if c == h.form.get("category") else ""}>{e(c)}</option>' for c in CATEGORIES)
    body = f"""<form method="post" class="card form">{h.csrf()}{err}
<label>분류<select name="category">{opts}</select></label>
<label>제목<input name="title" maxlength="120" value="{e(h.form.get('title', ''))}" required></label>
<label>내용<textarea name="body" rows="12" maxlength="5000" required>{e(h.form.get('body', ''))}</textarea></label>
<div class="row"><a class="btn" href="/board">취소</a><button class="btn primary">등록</button></div></form>"""
    h.page("글쓰기", "board", body)


@route("POST", r"/board/new")
def post_create(h):
    cat, title, text = h.form.get("category", ""), h.form.get("title", "")[:120], h.form.get("body", "")[:5000]
    if cat not in CATEGORIES or not title or not text:
        return post_new(h, "분류, 제목, 내용을 모두 입력해 주세요.")
    cur = h.db.execute("INSERT INTO posts(category,title,body,author_id,created) VALUES(?,?,?,?,?)",
                       (cat, title, text, h.user["id"], now_str()))
    h.db.commit()
    h.redirect(f"/board/{cur.lastrowid}?m=posted")


@route("GET", r"/board/(\d+)")
def post_view(h, pid):
    h.db.execute("UPDATE posts SET views=views+1 WHERE id=?", (pid,))
    h.db.commit()
    r = h.db.execute("""SELECT p.*, u.name, u.dept, u.id uid FROM posts p JOIN users u ON u.id=p.author_id
                        WHERE p.id=?""", (pid,)).fetchone()
    if not r:
        return h.fail(404, "게시글을 찾을 수 없습니다")
    cs = h.db.execute("""SELECT c.*, u.name, u.id uid FROM comments c JOIN users u ON u.id=c.author_id
                         WHERE c.post_id=? ORDER BY c.id""", (pid,)).fetchall()
    c_html = "".join(
        f'<li>{avatar(c["uid"], c["name"], "sm")}<div><b>{e(c["name"])}</b><time>{e(c["created"])}</time>'
        f'<p>{nl2br(c["body"])}</p></div></li>' for c in cs)
    can_delete = r["author_id"] == h.user["id"] or h.is_admin
    delete = (f'<form method="post" action="/board/{pid}/delete">{h.csrf()}<button class="btn danger">삭제</button></form>'
              if can_delete else "")
    body = f"""<article class="card doc">
<h2><span class="tag">{e(r['category'])}</span>{e(r['title'])}</h2>
<div class="meta">{avatar(r['uid'], r['name'], 'sm')}<span>{e(r['name'])} · {e(r['dept'])}</span>
<time>{e(r['created'])} · 조회 {r['views']}</time></div>
<div class="text">{nl2br(r['body'])}</div></article>
<section class="card"><h3>댓글 {len(cs)}</h3><ul class="comments">{c_html}</ul>
<form method="post" action="/board/{pid}/comment" class="comment-form">{h.csrf()}
<textarea name="body" rows="2" maxlength="1000" placeholder="댓글을 입력하세요" required></textarea>
<button class="btn primary">등록</button></form></section>
<div class="row"><a class="btn" href="/board">목록</a>{delete}</div>"""
    h.page("게시판", "board", body)


@route("POST", r"/board/(\d+)/comment")
def comment_create(h, pid):
    text = h.form.get("body", "")[:1000]
    if text and h.db.execute("SELECT 1 FROM posts WHERE id=?", (pid,)).fetchone():
        h.db.execute("INSERT INTO comments(post_id,author_id,body,created) VALUES(?,?,?,?)",
                     (pid, h.user["id"], text, now_str()))
        h.db.commit()
    h.redirect(f"/board/{pid}")


@route("POST", r"/board/(\d+)/delete")
def post_delete(h, pid):
    r = h.db.execute("SELECT author_id FROM posts WHERE id=?", (pid,)).fetchone()
    if not r:
        return h.fail(404, "게시글을 찾을 수 없습니다")
    if r["author_id"] != h.user["id"] and not h.is_admin:
        return h.fail(403, "권한이 없습니다")
    h.db.execute("DELETE FROM comments WHERE post_id=?", (pid,))
    h.db.execute("DELETE FROM posts WHERE id=?", (pid,))
    h.db.commit()
    h.redirect("/board?m=deleted")


# ───────────────────────── 결재 ─────────────────────────
@route("GET", r"/approvals")
def approvals(h):
    tab = "sent" if h.q.get("tab") == "sent" else "inbox"
    if tab == "inbox":
        rows = h.db.execute("""SELECT a.*, u.name FROM approvals a JOIN users u ON u.id=a.drafter_id
                               WHERE a.approver_id=? ORDER BY a.status='pending' DESC, a.created DESC""",
                            (h.user["id"],)).fetchall()
        who = "기안자"
    else:
        rows = h.db.execute("""SELECT a.*, u.name FROM approvals a JOIN users u ON u.id=a.approver_id
                               WHERE a.drafter_id=? ORDER BY a.created DESC""", (h.user["id"],)).fetchall()
        who = "결재자"
    trs = "".join(
        f'<tr><td><span class="tag">{e(r["kind"])}</span></td><td><a href="/approvals/{r["id"]}">{e(r["title"])}</a></td>'
        f'<td>{e(r["name"])}</td><td class="dim">{e(r["created"][:10])}</td><td>{badge(r["status"])}</td></tr>' for r in rows)
    table = (f'<div class="card flush"><table><thead><tr><th>종류</th><th>제목</th><th>{who}</th><th>기안일</th>'
             f'<th>상태</th></tr></thead><tbody>{trs}</tbody></table></div>') if rows else empty("문서가 없습니다.")
    body = f"""<div class="toolbar"><nav class="tabs">
<a class="{'on' if tab == 'inbox' else ''}" href="/approvals">받은 결재</a>
<a class="{'on' if tab == 'sent' else ''}" href="/approvals?tab=sent">내 기안</a></nav></div>{table}"""
    h.page("결재", "approvals", body, '<a class="btn primary" href="/approvals/new">기안 작성</a>')


@route("GET", r"/approvals/new")
def approval_new(h, error=""):
    err = f'<p class="err">{e(error)}</p>' if error else ""
    kinds = "".join(f'<option{" selected" if k == h.form.get("kind") else ""}>{e(k)}</option>' for k in APPROVAL_KINDS)
    users = h.db.execute("SELECT id,name,dept,title FROM users WHERE id<>? ORDER BY dept,name", (h.user["id"],)).fetchall()
    chosen = to_int(h.form.get("approver_id"), 0)
    people = "".join(
        f'<option value="{r["id"]}"{" selected" if r["id"] == chosen else ""}>{e(r["dept"])} · {e(r["title"])} {e(r["name"])}</option>'
        for r in users)
    body = f"""<form method="post" class="card form">{h.csrf()}{err}
<div class="cols"><label>문서 종류<select name="kind">{kinds}</select></label>
<label>결재자<select name="approver_id">{people}</select></label></div>
<label>제목<input name="title" maxlength="120" value="{e(h.form.get('title', ''))}" required></label>
<label>내용<textarea name="body" rows="10" maxlength="5000" required>{e(h.form.get('body', ''))}</textarea></label>
<div class="row"><a class="btn" href="/approvals">취소</a><button class="btn primary">상신</button></div></form>"""
    h.page("기안 작성", "approvals", body)


@route("POST", r"/approvals/new")
def approval_create(h):
    kind, title, text = h.form.get("kind", ""), h.form.get("title", "")[:120], h.form.get("body", "")[:5000]
    approver = to_int(h.form.get("approver_id"), 0)
    ok = h.db.execute("SELECT 1 FROM users WHERE id=? AND id<>?", (approver, h.user["id"])).fetchone()
    if kind not in APPROVAL_KINDS or not title or not text or not ok:
        return approval_new(h, "모든 항목을 올바르게 입력해 주세요.")
    cur = h.db.execute("INSERT INTO approvals(kind,title,body,drafter_id,approver_id,created) VALUES(?,?,?,?,?,?)",
                       (kind, title, text, h.user["id"], approver, now_str()))
    h.db.commit()
    h.redirect(f"/approvals/{cur.lastrowid}?m=posted")


def load_approval(h, aid):
    """기안자·결재자·관리자만 열람할 수 있습니다. 그 외에는 존재 여부도 알려주지 않습니다."""
    r = h.db.execute("""SELECT a.*, d.name dname, d.dept ddept, d.title dtitle,
                        p.name pname, p.dept pdept, p.title ptitle
                        FROM approvals a JOIN users d ON d.id=a.drafter_id JOIN users p ON p.id=a.approver_id
                        WHERE a.id=?""", (aid,)).fetchone()
    if not r or (h.user["id"] not in (r["drafter_id"], r["approver_id"]) and not h.is_admin):
        return None
    return r


@route("GET", r"/approvals/(\d+)")
def approval_view(h, aid):
    r = load_approval(h, aid)
    if not r:
        return h.fail(404, "문서를 찾을 수 없습니다")
    decide = ""
    if r["status"] == "pending" and r["approver_id"] == h.user["id"]:
        decide = f"""<form method="post" action="/approvals/{aid}/decide" class="card form">{h.csrf()}
<h3>결재 처리</h3><label>의견 (선택)<textarea name="comment" rows="3" maxlength="500"></textarea></label>
<div class="row"><button class="btn danger" name="action" value="reject">반려</button>
<button class="btn primary" name="action" value="approve">승인</button></div></form>"""
    opinion = (f'<div class="opinion"><b>결재 의견</b><p>{nl2br(r["comment"])}</p></div>' if r["comment"] else "")
    body = f"""<article class="card doc">
<h2><span class="tag">{e(r['kind'])}</span>{e(r['title'])} {badge(r['status'])}</h2>
<div class="line">
  <div class="step done"><small>기안</small>{avatar(r['drafter_id'], r['dname'])}<b>{e(r['dtitle'])} {e(r['dname'])}</b>
  <span>{e(r['ddept'])}</span><time>{e(r['created'])}</time></div>
  <div class="step {e(r['status'])}"><small>결재</small>{avatar(r['approver_id'], r['pname'])}<b>{e(r['ptitle'])} {e(r['pname'])}</b>
  <span>{e(r['pdept'])}</span><time>{e(r['decided'] or '대기 중')}</time></div>
</div>
<div class="text">{nl2br(r['body'])}</div>{opinion}</article>
{decide}<div class="row"><a class="btn" href="/approvals">목록</a></div>"""
    h.page("결재", "approvals", body)


@route("POST", r"/approvals/(\d+)/decide")
def approval_decide(h, aid):
    r = load_approval(h, aid)
    if not r:
        return h.fail(404, "문서를 찾을 수 없습니다")
    action = h.form.get("action")
    if r["approver_id"] != h.user["id"] or r["status"] != "pending" or action not in ("approve", "reject"):
        return h.fail(403, "처리할 수 없는 문서입니다")
    h.db.execute("UPDATE approvals SET status=?, comment=?, decided=? WHERE id=? AND status='pending'",
                 ("approved" if action == "approve" else "rejected", h.form.get("comment", "")[:500] or None, now_str(), aid))
    h.db.commit()
    h.redirect(f"/approvals/{aid}?m=decided")


# ───────────────────────── 일정 ─────────────────────────
@route("GET", r"/calendar")
def calendar_view(h, error=""):
    today = dt.date.today()
    m = re.fullmatch(r"(\d{4})-(\d{2})", h.q.get("ym", ""))
    year, month = (int(m.group(1)), int(m.group(2))) if m else (today.year, today.month)
    if not (2000 <= year <= 2100 and 1 <= month <= 12):
        year, month = today.year, today.month
    weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(year, month)
    rows = h.db.execute("""SELECT * FROM events WHERE date BETWEEN ? AND ? AND (scope='company' OR owner_id=?)
                           ORDER BY date, time""", (str(weeks[0][0]), str(weeks[-1][-1]), h.user["id"])).fetchall()
    by_day = {}
    for r in rows:
        by_day.setdefault(r["date"], []).append(r)
    cells = []
    for week in weeks:
        for d in week:
            cls = ["day"]
            if d.month != month:
                cls.append("out")
            if d == today:
                cls.append("today")
            if d.weekday() == 6:
                cls.append("sun")
            evs = "".join(
                f'<span class="ev {e(r["scope"])}" title="{e(r["title"])}">{e((r["time"] + " ") if r["time"] else "")}{e(r["title"])}</span>'
                for r in by_day.get(str(d), []))
            cells.append(f'<div class="{" ".join(cls)}"><b>{d.day}</b>{evs}</div>')
    prev = (dt.date(year, month, 1) - dt.timedelta(days=1)).strftime("%Y-%m")
    nxt = (dt.date(year, month, 28) + dt.timedelta(days=7)).strftime("%Y-%m")
    month_rows = [r for r in rows if r["date"][:7] == f"{year}-{month:02d}"]
    items = ""
    for r in month_rows:
        can = r["owner_id"] == h.user["id"] or h.is_admin
        delete = (f'<form method="post" action="/calendar/{r["id"]}/delete">{h.csrf()}'
                  f'<input type="hidden" name="ym" value="{year}-{month:02d}"><button class="x" title="삭제">×</button></form>'
                  if can else "")
        items += (f'<li><span class="date"><b>{e(r["date"][8:10])}</b>{e(r["date"][5:7])}월</span>'
                  f'<span class="grow">{e(r["title"])}<small>{e(r["time"] or "종일")}{" · " + e(r["place"]) if r["place"] else ""}'
                  f' · {"부대" if r["scope"] == "company" else "개인"}</small></span>{delete}</li>')
    scope = ('<label>구분<select name="scope"><option value="personal">개인</option>'
             '<option value="company">부대</option></select></label>') if h.is_admin else ""
    err = f'<p class="err">{e(error)}</p>' if error else ""
    body = f"""<div class="cal-wrap">
<section class="card"><div class="cal-head"><a class="btn" href="/calendar?ym={prev}">‹</a>
<h2>{year}년 {month}월</h2><a class="btn" href="/calendar?ym={nxt}">›</a>
<a class="btn ghost" href="/calendar">오늘</a></div>
<div class="cal"><i>일</i><i>월</i><i>화</i><i>수</i><i>목</i><i>금</i><i>토</i>{''.join(cells)}</div>
<p class="legend"><span class="ev company">부대 일정</span><span class="ev personal">개인 일정</span></p></section>
<aside><form method="post" action="/calendar/new" class="card form">{h.csrf()}<h3>일정 추가</h3>{err}
<label>제목<input name="title" maxlength="60" required></label>
<div class="cols"><label>날짜<input type="date" name="date" value="{today}" required></label>
<label>시간<input type="time" name="time"></label></div>
<label>장소<input name="place" maxlength="40"></label>{scope}
<button class="btn primary wide">추가</button></form>
<section class="card"><h3>이번 달 일정</h3>{f'<ul class="agenda">{items}</ul>' if items else empty('일정이 없습니다.')}</section></aside>
</div>"""
    h.page("일정", "calendar", body)


@route("POST", r"/calendar/new")
def event_create(h):
    title, date, tm, place = (h.form.get(k, "") for k in ("title", "date", "time", "place"))
    try:
        dt.date.fromisoformat(date)
        valid = bool(title) and (not tm or re.fullmatch(r"[0-2]\d:[0-5]\d", tm))
    except ValueError:
        valid = False
    if not valid:
        return calendar_view(h, "제목과 날짜를 올바르게 입력해 주세요.")
    scope = "company" if h.is_admin and h.form.get("scope") == "company" else "personal"
    h.db.execute("INSERT INTO events(title,date,time,place,owner_id,scope) VALUES(?,?,?,?,?,?)",
                 (title[:60], date, tm, place[:40], h.user["id"], scope))
    h.db.commit()
    h.redirect(f"/calendar?ym={date[:7]}&m=saved")


@route("POST", r"/calendar/(\d+)/delete")
def event_delete(h, eid):
    r = h.db.execute("SELECT owner_id FROM events WHERE id=?", (eid,)).fetchone()
    if not r:
        return h.fail(404, "일정을 찾을 수 없습니다")
    if r["owner_id"] != h.user["id"] and not h.is_admin:
        return h.fail(403, "권한이 없습니다")
    h.db.execute("DELETE FROM events WHERE id=?", (eid,))
    h.db.commit()
    ym = h.form.get("ym", "")
    h.redirect(f"/calendar?ym={ym}&m=deleted" if re.fullmatch(r"\d{4}-\d{2}", ym) else "/calendar?m=deleted")


# ───────────────────────── 부대원 ─────────────────────────
@route("GET", r"/people")
def people(h):
    term = h.q.get("q", "").strip()[:30]
    depts = [r[0] for r in h.db.execute("SELECT DISTINCT dept FROM users ORDER BY dept")]
    dept = h.q.get("dept", "") if h.q.get("dept") in depts else ""
    where, args = [], []
    if dept:
        where.append("dept=?")
        args.append(dept)
    if term:
        where.append("(name LIKE ? ESCAPE '\\' OR title LIKE ? ESCAPE '\\' OR email LIKE ? ESCAPE '\\')")
        args += [like(term)] * 3
    clause = "WHERE " + " AND ".join(where) if where else ""
    rows = h.db.execute(f"SELECT * FROM users {clause} ORDER BY dept, joined", args).fetchall()
    tabs = "".join(
        f'<a class="{"on" if d == dept else ""}" href="/people?{e(urlencode({k: v for k, v in (("dept", d), ("q", term)) if v}))}">'
        f'{e(d or "전체")}</a>' for d in [""] + depts)
    cards = "".join(f"""<div class="person">{avatar(r['id'], r['name'], 'lg')}
<b><small>{e(r['title'])}</small> {e(r['name'])}</b><span class="tag">{e(r['dept'])}</span>
<dl><dt>메일</dt><dd><a href="mailto:{e(r['email'])}">{e(r['email'])}</a></dd>
<dt>휴대폰</dt><dd>{e(r['phone'])}</dd><dt>군 전화</dt><dd>{e(r['ext'])}</dd><dt>전입</dt><dd>{e(r['joined'])}</dd></dl></div>"""
                    for r in rows)
    body = f"""<div class="toolbar"><nav class="tabs">{tabs}</nav>
<form class="search" method="get" action="/people"><input type="hidden" name="dept" value="{e(dept)}">
<input name="q" value="{e(term)}" placeholder="이름·계급·메일 검색" maxlength="30"><button class="btn">검색</button></form></div>
{f'<div class="people">{cards}</div>' if rows else empty('검색 결과가 없습니다.')}"""
    h.page(f"부대원 {len(rows)}명", "people", body)


# ───────────────────────── 내 정보 ─────────────────────────
@route("GET", r"/me")
def me(h, error=""):
    u = h.user
    err = f'<p class="err">{e(error)}</p>' if error else ""
    body = f"""<div class="grid2">
<form method="post" action="/me" class="card form">{h.csrf()}<h3>내 정보</h3>
<div class="profile">{avatar(u['id'], u['name'], 'lg')}<div><b>{e(u['title'])} {e(u['name'])}</b>
<span>{e(u['dept'])} · {e(u['email'])}</span><span>전입일 {e(u['joined'])}{' · 관리자' if h.is_admin else ''}</span></div></div>
<label>휴대폰<input name="phone" value="{e(u['phone'])}" maxlength="20" pattern="[0-9\\-+ ]*"></label>
<label>군 전화<input name="ext" value="{e(u['ext'])}" maxlength="6" pattern="[0-9]*"></label>
<button class="btn primary">저장</button></form>
<form method="post" action="/me/password" class="card form">{h.csrf()}<h3>비밀번호 변경</h3>{err}
<label>현재 비밀번호<input type="password" name="current" autocomplete="current-password" required></label>
<label>새 비밀번호 (8자 이상, 영문+숫자)<input type="password" name="new" autocomplete="new-password" minlength="8" required></label>
<label>새 비밀번호 확인<input type="password" name="confirm" autocomplete="new-password" minlength="8" required></label>
<button class="btn primary">변경</button></form></div>"""
    h.page("내 정보", "", body)


@route("POST", r"/me")
def me_save(h):
    phone = re.sub(r"[^0-9\-+ ]", "", h.form.get("phone", ""))[:20]
    ext = re.sub(r"\D", "", h.form.get("ext", ""))[:6]
    h.db.execute("UPDATE users SET phone=?, ext=? WHERE id=?", (phone, ext, h.user["id"]))
    h.db.commit()
    h.redirect("/me?m=saved")


@route("POST", r"/me/password")
def me_password(h):
    current, new, confirm = (h.form.get(k, "") for k in ("current", "new", "confirm"))
    if not check_pw(current, h.user["pw"]):
        return me(h, "현재 비밀번호가 올바르지 않습니다.")
    if new != confirm:
        return me(h, "새 비밀번호가 서로 다릅니다.")
    if len(new) < 8 or len(new) > 200 or not re.search(r"[A-Za-z]", new) or not re.search(r"\d", new):
        return me(h, "비밀번호는 8자 이상이며 영문과 숫자를 모두 포함해야 합니다.")
    if new.lower() == h.user["username"].lower() or new == current:
        return me(h, "아이디와 같거나 기존과 같은 비밀번호는 쓸 수 없습니다.")
    h.db.execute("UPDATE users SET pw=? WHERE id=?", (hash_pw(new), h.user["id"]))
    h.db.execute("DELETE FROM sessions WHERE user_id=? AND token<>?", (h.user["id"], h.sess["token"]))
    h.db.commit()
    h.redirect("/me?m=pw")


# ───────────────────────── 스타일 ─────────────────────────
CSS = r"""
:root{--bg:#eceae0;--panel:#fbfaf5;--ink:#20261c;--dim:#676d5c;--line:#d5d2c2;--side:#1e2a1c;--side-ink:#aab39e;
--acc:#4a6332;--acc-ink:#fff;--acc-soft:#e2e8d4;--warn:#96691a;--warn-soft:#f6ecd2;--bad:#b23a33;--bad-soft:#f7e4e1;
--radius:6px;--shadow:0 1px 2px rgba(30,42,28,.06)}
@media (prefers-color-scheme:dark){:root{--bg:#11150e;--panel:#1a2016;--ink:#e6e8df;--dim:#949b88;--line:#2c3426;
--side:#0b0e09;--acc:#9db56f;--acc-ink:#141a0e;--acc-soft:#27311c;--warn:#e0b25a;--warn-soft:#33290f;--bad:#f0837b;--bad-soft:#3a1c1a;
--shadow:0 1px 2px rgba(0,0,0,.3)}}
*{box-sizing:border-box}
html{font-size:15px}
body{margin:0;background:var(--bg);color:var(--ink);line-height:1.55;
font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",system-ui,sans-serif;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
h1,h2,h3,p{margin:0}
small{color:var(--dim)}
code{background:var(--acc-soft);color:var(--acc);padding:1px 6px;border-radius:5px;font-size:.92em}
.app{display:grid;grid-template-columns:232px 1fr;min-height:100vh}
.side{background:var(--side);color:var(--side-ink);display:flex;flex-direction:column;padding:22px 14px;position:sticky;top:0;height:100vh}
.brand{display:flex;align-items:center;gap:10px;color:#fff;font-weight:800;font-size:1.12rem;letter-spacing:-.02em;padding:0 8px 22px}
.brand i{width:30px;height:30px;border-radius:9px;background:linear-gradient(135deg,#3dc39f,#0f8a6c 60%,#0a5f7a);box-shadow:inset 0 0 0 2px rgba(255,255,255,.18)}
.brand span{display:flex;flex-direction:column;line-height:1.1}
.brand small{color:#7f89a3;font-weight:500;font-size:.7rem;letter-spacing:.14em;text-transform:uppercase}
.side nav{display:flex;flex-direction:column;gap:2px;flex:1}
.nav{display:flex;align-items:center;gap:11px;padding:10px 12px;border-radius:10px;font-weight:500;transition:background .15s,color .15s}
.nav svg{width:19px;height:19px;flex:none}
.nav:hover{background:rgba(255,255,255,.06);color:#fff}
.nav.on{background:rgba(61,195,159,.16);color:#fff}
.nav.on svg{color:#3dc39f}
.cnt{margin-left:auto;background:#3dc39f;color:#06241c;font-size:.72rem;border-radius:99px;padding:1px 8px}
.me{display:flex;align-items:center;gap:10px;padding:10px;border-radius:12px;background:rgba(255,255,255,.05)}
.me:hover{background:rgba(255,255,255,.09)}
.me span{display:flex;flex-direction:column;line-height:1.25;min-width:0}
.me b{color:#fff;font-size:.9rem;font-weight:600}
.me small{color:#7f89a3;font-size:.78rem}
.main{min-width:0}
.top{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:20px 32px 0}
.top h1{font-size:1.45rem;letter-spacing:-.03em}
.top-r{display:flex;gap:8px;align-items:center}
.content{padding:20px 32px 48px;max-width:1180px;display:flex;flex-direction:column;gap:18px}
.flash{margin:14px 32px 0;padding:10px 14px;border-radius:10px;background:var(--acc-soft);color:var(--acc);font-weight:600;max-width:1116px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:20px 22px;box-shadow:var(--shadow)}
.card.flush{padding:0;overflow:hidden}
.card h3{font-size:1rem;display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
.card h3 a{font-size:.8rem;color:var(--dim);font-weight:500}
.card h3 a:hover{color:var(--acc)}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;border:1px solid var(--line);background:var(--panel);color:var(--ink);
padding:8px 14px;border-radius:10px;font:inherit;font-weight:600;font-size:.9rem;cursor:pointer;white-space:nowrap;transition:transform .1s,border-color .15s}
.btn:hover{border-color:var(--dim)}
.btn:active{transform:translateY(1px)}
.btn.primary{background:var(--acc);border-color:var(--acc);color:var(--acc-ink)}
.btn.danger{color:var(--bad);border-color:var(--bad-soft);background:var(--bad-soft)}
.btn.ghost{background:transparent;color:var(--dim)}
.btn.wide{width:100%}
:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
.hero{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:26px 28px;border-radius:18px;color:#fff;
background:radial-gradient(120% 160% at 100% 0,#1f9c7d 0,#14506a 45%,#141a2b 100%)}
.hero h2{font-size:1.5rem;letter-spacing:-.03em}
.hero p{opacity:.75;margin-top:4px}
.hero .btn{background:#fff;color:#141a2b;border-color:#fff}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:16px 18px;display:flex;flex-direction:column;gap:2px;box-shadow:var(--shadow);transition:border-color .15s}
.stat:hover{border-color:var(--acc)}
.stat b{font-size:1.9rem;letter-spacing:-.04em;font-variant-numeric:tabular-nums}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:start}
.list,.agenda,.comments{list-style:none;margin:0;padding:0}
.list li{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-top:1px solid var(--line)}
.list li:first-child{border-top:0}
.list a{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.list a:hover{color:var(--acc)}
time,.dim{color:var(--dim);font-size:.85rem;white-space:nowrap}
em{font-style:normal;color:var(--acc);font-size:.85rem;font-weight:600}
.tag{display:inline-block;font-size:.74rem;font-weight:600;padding:2px 8px;border-radius:6px;background:var(--bg);border:1px solid var(--line);color:var(--dim);margin-right:8px;vertical-align:1px}
.pin{display:inline-block;font-size:.72rem;font-weight:700;padding:2px 7px;border-radius:6px;background:var(--warn-soft);color:var(--warn);margin-right:8px}
.badge{display:inline-block;font-size:.76rem;font-weight:700;padding:2px 10px;border-radius:99px}
.badge.pending{background:var(--warn-soft);color:var(--warn)}
.badge.approved{background:var(--acc-soft);color:var(--acc)}
.badge.rejected{background:var(--bad-soft);color:var(--bad)}
.empty{color:var(--dim);text-align:center;padding:26px 0}
.agenda li{display:flex;align-items:center;gap:14px;padding:9px 0;border-top:1px solid var(--line)}
.agenda li:first-child{border-top:0}
.date{display:flex;flex-direction:column;align-items:center;width:44px;font-size:.72rem;color:var(--dim);line-height:1.1;flex:none}
.date b{font-size:1.2rem;color:var(--ink)}
.grow{flex:1;display:flex;flex-direction:column;min-width:0}
.x{border:0;background:none;color:var(--dim);font-size:1.2rem;cursor:pointer;border-radius:6px;padding:0 6px}
.x:hover{color:var(--bad);background:var(--bad-soft)}
table{width:100%;border-collapse:collapse}
th{text-align:left;font-size:.78rem;color:var(--dim);font-weight:600;padding:11px 16px;border-bottom:1px solid var(--line);background:var(--bg)}
td{padding:12px 16px;border-top:1px solid var(--line)}
tbody tr:first-child td{border-top:0}
tbody tr:hover{background:color-mix(in srgb,var(--acc-soft) 45%,transparent)}
td a:hover{color:var(--acc)}
.num{text-align:center;width:72px;font-variant-numeric:tabular-nums}
.toolbar{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.tabs{display:flex;gap:4px;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:4px;flex-wrap:wrap}
.tabs a{padding:6px 14px;border-radius:9px;font-weight:600;font-size:.88rem;color:var(--dim)}
.tabs a.on{background:var(--ink);color:var(--panel)}
.search{display:flex;gap:6px}
input,select,textarea{font:inherit;color:var(--ink);background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:9px 12px;width:100%}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--acc);box-shadow:0 0 0 3px var(--acc-soft)}
textarea{resize:vertical}
.search input{width:220px}
.form{display:flex;flex-direction:column;gap:14px}
.form label{display:flex;flex-direction:column;gap:6px;font-size:.84rem;font-weight:600;color:var(--dim)}
.form label.check{flex-direction:row;align-items:center;gap:8px}
.check input{width:auto}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.cols>*{min-width:0}
.row{display:flex;justify-content:flex-end;gap:8px}
.err,.info{padding:10px 12px;border-radius:10px;font-weight:600;font-size:.9rem}
.err{background:var(--bad-soft);color:var(--bad)}
.info{background:var(--acc-soft);color:var(--acc)}
.pager{display:flex;justify-content:center;gap:4px}
.pager a{min-width:34px;text-align:center;padding:6px 0;border-radius:9px;border:1px solid var(--line);background:var(--panel);font-weight:600}
.pager a.on{background:var(--ink);color:var(--panel);border-color:var(--ink)}
.doc h2{font-size:1.3rem;letter-spacing:-.02em;line-height:1.35}
.meta{display:flex;align-items:center;gap:10px;color:var(--dim);font-size:.88rem;padding:12px 0 16px;border-bottom:1px solid var(--line)}
.meta time{margin-left:auto}
.text{padding-top:18px;font-size:1.02rem;line-height:1.8;overflow-wrap:anywhere}
.comments li{display:flex;gap:12px;padding:12px 0;border-top:1px solid var(--line)}
.comments b{margin-right:8px}
.comments p{margin-top:2px;overflow-wrap:anywhere}
.comment-form{display:flex;gap:8px;align-items:flex-end;margin-top:8px}
.av{display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;border-radius:50%;color:#fff;font-weight:700;flex:none}
.av.sm{width:28px;height:28px;font-size:.8rem}
.av.lg{width:56px;height:56px;font-size:1.3rem}
.c0{background:#0f8a6c}.c1{background:#2f6fde}.c2{background:#b7791f}.c3{background:#8a4fd3}.c4{background:#c2413a}.c5{background:#3a8194}
.line{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:16px 0 4px}
.step{display:grid;grid-template-columns:auto 1fr;column-gap:12px;align-items:center;border:1px solid var(--line);border-radius:12px;padding:12px 14px;background:var(--bg)}
.step small{grid-column:1/-1;font-weight:700;letter-spacing:.08em;margin-bottom:6px}
.step .av{grid-row:span 3}
.step span,.step time{color:var(--dim);font-size:.84rem}
.step.approved{border-color:var(--acc)}
.step.rejected{border-color:var(--bad)}
.opinion{margin-top:18px;padding:14px 16px;border-radius:12px;background:var(--bg);border-left:3px solid var(--acc)}
.cal-wrap{display:grid;grid-template-columns:1fr 300px;gap:18px;align-items:start}
.cal-wrap aside{display:flex;flex-direction:column;gap:18px}
.cal-head{display:flex;align-items:center;gap:10px;margin-bottom:14px}
.cal-head h2{font-size:1.2rem;min-width:120px;text-align:center}
.cal-head .ghost{margin-left:auto}
.cal{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));border-top:1px solid var(--line);border-left:1px solid var(--line);border-radius:10px;overflow:hidden}
.cal i{font-style:normal;text-align:center;font-size:.76rem;font-weight:600;color:var(--dim);padding:7px 0;background:var(--bg);border-right:1px solid var(--line);border-bottom:1px solid var(--line)}
.day{min-height:92px;padding:6px;border-right:1px solid var(--line);border-bottom:1px solid var(--line);display:flex;flex-direction:column;gap:3px}
.day b{font-size:.82rem;font-weight:600;width:24px;height:24px;display:flex;align-items:center;justify-content:center;border-radius:50%}
.day.out{background:var(--bg)}
.day.out b{color:var(--dim);opacity:.5}
.day.sun b{color:var(--bad)}
.day.today b{background:var(--acc);color:var(--acc-ink)}
.ev{font-size:.72rem;padding:2px 6px;border-radius:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:600}
.ev.company{background:var(--acc-soft);color:var(--acc)}
.ev.personal{background:var(--warn-soft);color:var(--warn)}
.legend{display:flex;gap:8px;margin-top:12px}
.people{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}
.person{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:18px;display:flex;flex-direction:column;align-items:flex-start;gap:8px;box-shadow:var(--shadow)}
.person b small{font-weight:500}
dl{display:grid;grid-template-columns:52px 1fr;gap:3px 8px;margin:6px 0 0;font-size:.86rem;width:100%}
dt{color:var(--dim)}
dd{margin:0;overflow:hidden;text-overflow:ellipsis}
dd a:hover{color:var(--acc)}
.profile{display:flex;gap:14px;align-items:center;padding-bottom:6px}
.profile div{display:flex;flex-direction:column}
.profile span{color:var(--dim);font-size:.86rem}
.login{display:grid;grid-template-columns:1.1fr 1fr;min-height:100vh}
.login-art{background:radial-gradient(130% 120% at 0 100%,#1f9c7d 0,#14506a 40%,#141a2b 85%);color:#fff;padding:48px;display:flex;flex-direction:column;justify-content:flex-end;gap:12px}
.login-art .brand{position:absolute;top:40px;left:48px;padding:0}
.login-art h2{font-size:2.8rem;line-height:1.15;letter-spacing:-.04em}
.login-art p{opacity:.7}
.login-form{display:flex;align-items:center;justify-content:center;padding:32px}
.login-form .card{width:100%;max-width:380px;display:flex;flex-direction:column;gap:14px;padding:30px}
.login-form h1{font-size:1.5rem;letter-spacing:-.03em}
.login-form label{display:flex;flex-direction:column;gap:6px;font-size:.84rem;font-weight:600;color:var(--dim)}
.hint{font-size:.84rem;color:var(--dim);border-top:1px dashed var(--line);padding-top:14px;line-height:1.9}
.lone{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}
.center{text-align:center;display:flex;flex-direction:column;gap:12px;align-items:center;padding:40px 56px}
.code{font-size:3.4rem;font-weight:800;letter-spacing:-.05em;color:var(--acc)}
@media (max-width:900px){
.app{grid-template-columns:1fr}
.side{position:static;height:auto;flex-direction:row;align-items:center;padding:10px;gap:8px;overflow-x:auto}
.brand{padding:0 6px}.brand span,.me span,.nav span{display:none}
.side nav{flex-direction:row}.me{background:none;padding:4px}
.top{padding:16px 16px 0}.content{padding:16px}.flash{margin:12px 16px 0}
.stats{grid-template-columns:1fr 1fr}.grid2,.cal-wrap,.line,.cols{grid-template-columns:1fr}
.login{grid-template-columns:1fr}.login-art{display:none}
.day{min-height:64px}.search input{width:140px}
td:nth-child(3),th:nth-child(3){display:none}
}

/* ── 군 테마 ── */
.classbar{position:sticky;top:0;z-index:5;height:26px;line-height:26px;text-align:center;font-size:.76rem;font-weight:700;letter-spacing:.12em;background:#2f6b3a;color:#fff}
.app{min-height:calc(100vh - 26px)}
.side{top:26px;height:calc(100vh - 26px);border-right:3px solid #c9b26b}
.btn,input,select,textarea,.tabs,.tabs a,.nav,.me,.hero,.flash,.pager a,.step,.tag,.pin,.ev,.err,.info,.opinion,.cal,.badge,.cnt{border-radius:3px}
.brand i{display:flex;align-items:center;justify-content:center;font-style:normal;font-size:.95rem;color:#c9b26b;background:#2c3b26;border-radius:3px;box-shadow:inset 0 0 0 1px #c9b26b}
.brand small,.me small{color:#8d967f}
.nav.on{background:rgba(201,178,107,.14);box-shadow:inset 3px 0 0 #c9b26b}
.nav.on svg{color:#c9b26b}
.cnt{background:#c9b26b;color:#1b2416}
.hero{background:linear-gradient(100deg,#263522 0,#3d5230 60%,#56683a 100%);border-bottom:3px solid #c9b26b}
.hero .btn{color:#20261c}
.top h1{border-left:4px solid var(--acc);padding-left:10px}
th{text-transform:none;letter-spacing:.04em}
.c0{background:#4a6332}.c1{background:#3d5a73}.c2{background:#8a6d2a}.c3{background:#5b5470}.c4{background:#8c4a3c}.c5{background:#46706a}
.login{min-height:calc(100vh - 26px)}
.login-art{background:linear-gradient(160deg,#1e2a1c 0,#33452a 55%,#56683a 100%);position:relative}
.login-art .brand{top:40px}
dl{grid-template-columns:62px 1fr}
@media (max-width:900px){.side{height:auto;top:0;border-right:0;border-bottom:3px solid #c9b26b}}
"""


def main():
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    shown = "127.0.0.1" if HOST in ("0.0.0.0", "") else HOST
    print(f"\n  {COMPANY} 인트라넷 실행 중  ->  http://{shown}:{PORT}")
    print("  데모 계정: admin / admin1234 , jykim / nova1234")
    print("  종료: Ctrl+C\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다.")
        server.server_close()


if __name__ == "__main__":
    main()
