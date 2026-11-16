# OpsWatch — 가상 국방망 인트라넷 교육 복제

로컬에서만 사용하는 **의도적으로 취약한 교육용** Django MTV 웹 애플리케이션입니다.  
실제 국방망, 공인 주소, 외부 시스템, 운영 자격 증명을 대상으로 하지 않습니다.

- 공개 포트: `127.0.0.1:8000` 만 바인딩
- 계정·토큰·FLAG: 전부 실습용 가짜 값
- 셸 진단: **실습 컨테이너 안에서만** 활성화
- 시나리오 설정: 가상 국방망 인트라넷에 침투한 뒤 진단 API 명령어 삽입

학습자는 가능하면 이 README의 계정 표를 보지 말고 `/staff/`부터 시작해도 됩니다.

## 시나리오

1. 공개 직원 안내에서 유지보수 계정 ID를 확인한다.
2. 추측하기 쉬운 실습 비밀번호로 로그인한다. 잠금은 없다.
3. 로그인 후 내부 토큰 발급 화면에서 고정된 가짜 API 토큰을 받는다.
4. 그 토큰만으로 세션 없이 `/api/internal/diagnose/`를 호출한다.
5. 진단 API가 입력값을 셸 문자열에 결합하는 지점을 이용해 컨테이너 내부 `/opt/challenge/flag.txt`를 읽는다.

스포일러가 포함된 풀이는 [`docs/WALKTHROUGH.md`](docs/WALKTHROUGH.md)입니다.

## MTV 구조

| 역할 | 위치 | 책임 |
| --- | --- | --- |
| Model | `inventory/models.py` | 직원, 서버, 점검 기록 |
| Template | `inventory/templates/inventory/` | 로그인, 직원 안내, 대시보드, 지원, 진단 |
| View | `inventory/views.py` | 요청, 인증 확인, 렌더링, JSON |
| URLconf | `opswatch/urls.py`, `inventory/urls.py` | 페이지·API 경로 |
| Service | `inventory/services/diagnostics.py` | 진단 실행(실습 전용) |
| Management | `inventory/management/commands/seed_lab.py` | 멱등 시드 |

Django 관리자 사이트는 연결하지 않습니다. `/admin/diagnostics/`는 실습용 진단 화면입니다.

## 필수 격리

Docker Compose는 아래를 강제합니다.

- 웹 포트 `127.0.0.1:8000:8000`
- MySQL 호스트 포트 없음
- `lab` 네트워크 `internal: true` (앱↔DB)
- `ingress`는 로컬 포트 공개용. 터널·공인 IP·추가 포트 금지
- 비루트 `uid 1000`, `privileged: false`, 호스트 네트워크/도커 소켓/호스트 바인드 마운트 없음
- 웹: 읽기 전용 루트 + tmpfs, `cap_drop: ALL`, `no-new-privileges`, CPU·메모리·PID 제한
- 진단: 시간 3초, 출력 8KiB, 동시 실행 1개
- 호스트에서 Django를 직접 띄우면 셸 진단은 403

컨테이너 격리는 커널 네임스페이스 수준입니다. 호스트 탈출·도커 소켓 실습은 이 프로젝트의 범위가 아닙니다. **가능하면 별도 실습 VM에서 실행하세요.**

## 설치와 실행

요구: Docker Compose v2, 로컬 전용.

```powershell
cd C:\Users\USER\Documents\opswatch
docker compose up --build
```

브라우저: [http://127.0.0.1:8000/staff/](http://127.0.0.1:8000/staff/)

MySQL이 healthy가 된 뒤 엔트리포인트가 `migrate`와 `seed_lab`을 실행합니다.

### 운영 개요의 실습 데이터

- 에이전트 CPU·메모리는 `seed_metrics=True`인 실습 호스트만 브라우저에서 3초마다 변동합니다. 실제 호스트/컨테이너 사용률을 수집하지 않으며 DB의 원본 값과 호스트 상태는 바꾸지 않습니다.
- 탭이 숨겨지면 갱신을 멈추고, 다시 열면 재개합니다. JavaScript를 끄면 저장된 최초 값만 표시합니다. `seed_metrics=False`인 호스트는 항상 저장된 값을 표시합니다.
- 알림 추이는 정보·주의·위험별 **12시간 시뮬레이션 예시**입니다. 시간별 건수와 피크는 실제 점검 기록과 무관합니다. 상단의 최근 점검 건수·통과/실패 및 하단 점검 표는 DB 기록입니다.
- 화면 변경을 실행 중인 Docker 환경에 반영하려면 `docker compose up -d --build web`을 실행한 뒤 대시보드를 새로고침합니다.

### 호스트에서 단위 테스트/화면만 (셸 진단 차단)

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
$env:OPSWATCH_DATABASE = "sqlite"
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py seed_lab
.\.venv\Scripts\python manage.py runserver 127.0.0.1:8000
```

## 실습 계정 (가짜)

운영자용입니다. 학습 시나리오는 직원 페이지에서 ID를 찾는 것입니다.

| 담당자 | 부서 | 로그인 ID | 비밀번호 |
| --- | --- | --- | --- |
| 박도윤 | 망당직 · 유지보수 | `maint` | `maint123` |
| 김서연 | 인력관리 | `seoyeon` | `seoyeon123` |
| 이민준 | 체계운영 | `minjun` | `minjun123` |
| 최하린 | 상황실 | `harin` | `harin123` |

모두 같은 접근 권한의 일반 실습 계정이며 관리자(`is_staff`, `is_superuser`) 권한은 없습니다. 비밀번호는 의도적으로 약하며 DB에는 Django 해시로 저장합니다. `seed_lab` 재실행 시 위 계정을 생성·갱신하고 비밀번호를 위 값으로 초기화합니다. 당직 연락망에는 로그인 ID만 표시합니다.

- 내부 토큰: `/api/internal/token/`가 고정값 반환
- FLAG: 컨테이너 `/opt/challenge/flag.txt`

## 종료 · 재시작 · 초기화

```powershell
docker compose stop          # 종료, 볼륨 유지
docker compose start         # 재시작
docker compose down          # 컨테이너/네트워크 삭제, named volume 유지
docker compose down -v       # 실습 데이터 초기화
docker compose up --build    # 다시 시드
```

`down -v`가 삭제하는 범위:

- Compose가 만든 컨테이너, `lab`/`ingress` 네트워크
- named volume `mysql_data` (직원·서버·점검·세션 테이블)
- FLAG 파일은 이미지에 다시 복사됨

삭제하지 않는 것: 호스트의 이 소스 트리, Docker 엔진 자체.

호스트 SQLite를 썼다면 `db.sqlite3`를 지운 뒤 `migrate` + `seed_lab`을 다시 실행합니다.

## 테스트

```powershell
$env:OPSWATCH_DATABASE = "sqlite"
.\.venv\Scripts\python manage.py check
.\.venv\Scripts\python manage.py makemigrations --check --dry-run
.\.venv\Scripts\python manage.py test
```

호스트 단위 테스트는 `subprocess`를 모의합니다. 실제 명령 삽입 확인은 컨테이너 안에서만 합니다.

## 안전 주의

- `127.0.0.1` 외 바인딩, ngrok/cloudflared 등 터널, 공인 NIC 배포 금지
- 실제 비밀번호·토큰·사내 호스트를 넣지 말 것
- 이 코드의 셸 결합을 다른 시스템에 복사하지 말 것
- 개선 방법은 [`docs/SECURE_CODING.md`](docs/SECURE_CODING.md)
