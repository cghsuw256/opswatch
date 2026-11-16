# -*- coding: utf-8 -*-
"""
================================================================================
 군 인트라넷 보안약점 실습 환경 (Secure Coding Lab)
 - 발표/교육용 로컬 데모 (KISA SW 보안약점 진단 가이드 기반)
--------------------------------------------------------------------------------
 실습 가능한 보안약점 4종
   1. 하드코드된 중요정보   (KISA 보안약점 #30, CWE-798 / CWE-259)
   2. 운영체제 명령어 삽입   (CWE-78, OS Command Injection)
   3. 취약한 비밀번호 허용   (CWE-521, Weak Password Requirements)
   4. 반복된 인증시도 제한 부재 (CWE-307, Improper Restriction of Auth Attempts)

 각 메뉴는 [취약한 버전] 과 [안전한 버전] 을 토글(mode=vuln / mode=safe)로
 비교하도록 구성되어 있습니다. 발표 시 "왜 취약한가 → 어떻게 고치는가"를
 한 화면에서 보여주기 위한 구조입니다.

 ※ 이 애플리케이션은 격리된 로컬 환경(127.0.0.1)에서 교육 목적으로만
   사용합니다. 외부에 공개/배포하지 마세요.
================================================================================
 실행 방법 (PyCharm)
   1) pip install flask
   2) app.py 실행 (또는 터미널:  python app.py)
   3) 브라우저에서 http://127.0.0.1:5000 접속
================================================================================
"""

import os
import re
import time
import sqlite3
import hashlib
import secrets
import subprocess
from datetime import datetime
from functools import wraps
from flask import Flask, request, session, redirect, url_for, render_template, g, flash

# ------------------------------------------------------------------------------
# [실습 1 - 취약] 하드코드된 중요정보
# ------------------------------------------------------------------------------
# 아래 상수들은 "소스코드에 민감정보를 직접 박아 넣은" 전형적인 취약 패턴입니다.
# 소스가 유출되거나 깃허브에 올라가면 그대로 노출됩니다.
# → 안전한 버전에서는 os.environ(환경변수)에서 읽어옵니다. (하단 get_secret 참고)
# ------------------------------------------------------------------------------
HARDCODED_SECRET_KEY = "mil_intra_2024_secret_key"      # 세션 암호화 키 하드코딩 (취약)
HARDCODED_DB_PASSWORD = "admin1234!"                     # DB 접속 비밀번호 하드코딩 (취약)
HARDCODED_API_TOKEN = "AKIA-DEMO-0000-1111-2222"         # 외부 API 토큰 하드코딩 (취약)
HARDCODED_ADMIN_PW = "admin"                             # 관리자 초기 비밀번호 하드코딩 (취약)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lab.db")

app = Flask(__name__)
# 발표 편의를 위해 세션 키는 하드코드 값을 쓰되, 안전 버전 설명과 함께 제공
app.secret_key = HARDCODED_SECRET_KEY

# 로그인 실패 횟수 저장용 (실습 4) -- 메모리 기반 간이 저장소
FAILED_ATTEMPTS = {}   # { username: {"count": int, "locked_until": float} }
MAX_ATTEMPTS = 5
LOCK_SECONDS = 30


# ==============================================================================
# DB 초기화
# ==============================================================================
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            rank TEXT DEFAULT '이병'
        )
    """)
    # 기본 계정 (관리자) - 실습 4 브루트포스 대상
    cur.execute("SELECT COUNT(*) FROM users WHERE username='admin'")
    if cur.fetchone()[0] == 0:
        pw_hash = hashlib.sha256("Soldier!2024".encode()).hexdigest()
        cur.execute(
            "INSERT INTO users (username, password_hash, rank) VALUES (?,?,?)",
            ("admin", pw_hash, "대령"),
        )
    conn.commit()
    conn.close()


# ==============================================================================
# [안전] 하드코드 대신 환경변수에서 비밀값 읽기
# ==============================================================================
def get_secret(name, default=None):
    """
    안전한 버전: 민감정보는 소스가 아니라 환경변수/비밀관리도구에서 읽는다.
    예) 운영: os.environ["MIL_DB_PASSWORD"] / python-dotenv / Vault / KMS 등
    """
    return os.environ.get(name, default)


# ==============================================================================
# 공통 유틸
# ==============================================================================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def current_mode():
    """쿼리스트링 mode=safe 면 안전 버전, 그 외는 취약 버전."""
    return "safe" if request.args.get("mode") == "safe" else "vuln"


# 템플릿 공통 변수(실감나는 상단바/푸터용) ------------------------------------
SYSTEM_NAME = "SENTINEL"
SYSTEM_FULL = "통합전장정보체계"
UNIT_NAME = "GARUDA 전술사령부"
SYSTEM_VER = "v4.2.7"


@app.context_processor
def inject_globals():
    return {
        "now": datetime.now(),
        "SYSTEM_NAME": SYSTEM_NAME,
        "SYSTEM_FULL": SYSTEM_FULL,
        "UNIT_NAME": UNIT_NAME,
        "SYSTEM_VER": SYSTEM_VER,
        "client_ip": request.remote_addr or "127.0.0.1",
    }


# ==============================================================================
# 메인
# ==============================================================================
@app.route("/")
def index():
    return render_template("index.html", user=session.get("user"))


# ==============================================================================
# 실습 1) 하드코드된 중요정보
# ==============================================================================
@app.route("/lab/hardcoded")
def lab_hardcoded():
    mode = current_mode()

    if mode == "vuln":
        # [취약] 소스에 박힌 값을 그대로 화면/설정에 노출
        exposed = {
            "SECRET_KEY": HARDCODED_SECRET_KEY,
            "DB_PASSWORD": HARDCODED_DB_PASSWORD,
            "API_TOKEN": HARDCODED_API_TOKEN,
            "ADMIN_PW": HARDCODED_ADMIN_PW,
        }
        source_snippet = (
            'HARDCODED_DB_PASSWORD = "admin1234!"   # 소스에 직접 노출\n'
            'HARDCODED_API_TOKEN   = "AKIA-DEMO-..." # 깃허브 유출 시 그대로 탈취'
        )
    else:
        # [안전] 환경변수에서 읽고, 값이 없으면 "미설정"으로 표기(마스킹)
        def mask(v):
            if not v:
                return "(환경변수 미설정)"
            return v[:2] + "*" * (len(v) - 2)
        exposed = {
            "SECRET_KEY": mask(get_secret("MIL_SECRET_KEY")),
            "DB_PASSWORD": mask(get_secret("MIL_DB_PASSWORD")),
            "API_TOKEN": mask(get_secret("MIL_API_TOKEN")),
            "ADMIN_PW": "(DB에 해시로만 저장, 평문 없음)",
        }
        source_snippet = (
            'DB_PASSWORD = os.environ.get("MIL_DB_PASSWORD")  # 소스에 값 없음\n'
            'API_TOKEN   = os.environ.get("MIL_API_TOKEN")    # 유출돼도 토큰 안전'
        )

    return render_template(
        "hardcoded.html", mode=mode, exposed=exposed, source_snippet=source_snippet
    )


# ==============================================================================
# 실습 2) 운영체제 명령어 삽입 (OS Command Injection)
#   - 시나리오: 관리자용 '네트워크 점검(ping)' 기능
# ==============================================================================
@app.route("/lab/cmdi", methods=["GET", "POST"])
def lab_cmdi():
    mode = current_mode()
    result = None
    executed = None

    if request.method == "POST":
        target = request.form.get("target", "").strip()

        if mode == "vuln":
            # [취약] 사용자 입력을 셸 문자열에 그대로 이어붙여 shell=True 로 실행.
            #   공격 예:  127.0.0.1 ; whoami    또는    127.0.0.1 && dir
            #   세미콜론/앰퍼샌드로 임의 명령이 함께 실행된다.
            if os.name == "nt":
                cmd = "ping -n 1 " + target          # Windows
            else:
                cmd = "ping -c 1 " + target          # Linux/Mac
            executed = cmd
            try:
                out = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=5
                )
                result = (out.stdout or "") + (out.stderr or "")
            except Exception as e:
                result = f"[오류] {e}"
        else:
            # [안전] 1) 입력값 화이트리스트 검증(허용된 호스트 형식만)
            #        2) shell=False + 인자를 리스트로 전달 → 셸 해석 자체를 제거
            if not re.fullmatch(r"[A-Za-z0-9_.\-]{1,64}", target):
                result = "[차단] 허용되지 않은 입력입니다. (영문/숫자/.-_ 만 가능)"
                executed = "(실행 안 함)"
            else:
                flag = "-n" if os.name == "nt" else "-c"
                args = ["ping", flag, "1", target]    # 리스트 전달 = 인자 고정
                executed = " ".join(args) + "   (shell=False)"
                try:
                    out = subprocess.run(
                        args, shell=False, capture_output=True, text=True, timeout=5
                    )
                    result = (out.stdout or "") + (out.stderr or "")
                except Exception as e:
                    result = f"[오류] {e}"

    return render_template(
        "cmdi.html", mode=mode, result=result, executed=executed
    )


# ==============================================================================
# 실습 3) 취약한 비밀번호 허용 (Weak Password)
# ==============================================================================
PASSWORD_RULES = [
    (lambda p: len(p) >= 9, "9자 이상"),
    (lambda p: re.search(r"[A-Z]", p), "영문 대문자 포함"),
    (lambda p: re.search(r"[a-z]", p), "영문 소문자 포함"),
    (lambda p: re.search(r"[0-9]", p), "숫자 포함"),
    (lambda p: re.search(r"[^A-Za-z0-9]", p), "특수문자 포함"),
    (lambda p: not re.search(r"(.)\1\1", p), "같은 문자 3회 연속 금지"),
]
COMMON_PASSWORDS = {"1234", "0000", "password", "admin", "qwerty", "111111", "123456"}


def check_password_strength(pw):
    failed = []
    for rule, label in PASSWORD_RULES:
        if not rule(pw):
            failed.append(label)
    if pw.lower() in COMMON_PASSWORDS:
        failed.append("흔한 비밀번호 사용 금지")
    return failed


@app.route("/lab/weakpw", methods=["GET", "POST"])
def lab_weakpw():
    mode = current_mode()
    message = None
    ok = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        pw = request.form.get("password", "")

        if mode == "vuln":
            # [취약] 아무 검증 없이 가입 허용 → "1234" 같은 약한 비번도 통과
            ok = True
            message = f"가입 완료! (입력한 비밀번호: '{pw}') — 검증 없이 그대로 허용됨"
        else:
            # [안전] 비밀번호 복잡도 정책 강제
            failed = check_password_strength(pw)
            if failed:
                ok = False
                message = "가입 거부 — 미충족 정책: " + ", ".join(failed)
            else:
                ok = True
                message = "가입 완료! 비밀번호 정책을 모두 충족했습니다."

    return render_template(
        "weakpw.html", mode=mode, message=message, ok=ok, rules=PASSWORD_RULES
    )


# ==============================================================================
# 실습 4) 반복된 인증시도 제한 부재 (Brute-force)
# ==============================================================================
def verify_user(username, pw):
    db = get_db()
    row = db.execute(
        "SELECT password_hash FROM users WHERE username=?", (username,)
    ).fetchone()
    if not row:
        return False
    return row["password_hash"] == hashlib.sha256(pw.encode()).hexdigest()


@app.route("/lab/login", methods=["GET", "POST"])
def login():
    mode = current_mode()
    message = None
    locked_info = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        pw = request.form.get("password", "")

        if mode == "vuln":
            # [취약] 실패 횟수 제한이 전혀 없음 → 무제한 비밀번호 대입 가능
            if verify_user(username, pw):
                session["user"] = username
                message = "로그인 성공!"
            else:
                message = "아이디 또는 비밀번호가 올바르지 않습니다. (시도 횟수 제한 없음)"
        else:
            # [안전] 계정별 실패 횟수 카운트 + 임계치 초과 시 일시 잠금
            now = time.time()
            rec = FAILED_ATTEMPTS.get(username, {"count": 0, "locked_until": 0})

            if rec["locked_until"] > now:
                remain = int(rec["locked_until"] - now)
                message = f"[잠금] 로그인 시도가 너무 많습니다. {remain}초 후 다시 시도하세요."
                locked_info = remain
            elif verify_user(username, pw):
                FAILED_ATTEMPTS[username] = {"count": 0, "locked_until": 0}
                session["user"] = username
                message = "로그인 성공!"
            else:
                rec["count"] += 1
                if rec["count"] >= MAX_ATTEMPTS:
                    rec["locked_until"] = now + LOCK_SECONDS
                    rec["count"] = 0
                    message = f"[잠금] 실패 {MAX_ATTEMPTS}회 초과 — {LOCK_SECONDS}초간 계정 잠금."
                else:
                    left = MAX_ATTEMPTS - rec["count"]
                    message = f"로그인 실패. 남은 시도 {left}회 후 잠깁니다."
                FAILED_ATTEMPTS[username] = rec

    return render_template(
        "login.html", mode=mode, message=message,
        user=session.get("user"), max_attempts=MAX_ATTEMPTS, lock_seconds=LOCK_SECONDS
    )


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))


# ==============================================================================
if __name__ == "__main__":
    init_db()
    print("=" * 60)
    print(" [교육용] SENTINEL 통합전장정보체계 실습 서버 시작")
    print(" ※ 의도적 취약 환경 — 로컬에서만 사용, 외부 공개 금지")
    print(" 접속 주소:  http://127.0.0.1:5000")
    print(" 종료: Ctrl + C")
    print("=" * 60)
    # 교육용: 로컬에서만 접속 (0.0.0.0 로 열지 말 것)
    app.run(host="127.0.0.1", port=5000, debug=True)
