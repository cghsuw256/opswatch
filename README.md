# OpsWatch — 국방망 인트라넷 모의 진단 교육 환경

로컬에서만 사용하는 **의도적으로 취약한 교육용** Django MTV 웹 애플리케이션입니다.
실제 국방망, 공인 주소, 외부 시스템, 운영 자격 증명을 대상으로 하지 않습니다.

- 공개 포트: `127.0.0.1:8000` 만 바인딩
- 계정·토큰·FLAG: 전부 실습용 가짜 값
- 셸 진단: **격리된 실습 컨테이너 안에서만** 실제 실행
- 화면 구성: 로그인 후 부대 인트라넷 홈, 공지사항·게시판·결재·일정·부대원·내 정보. 기존 OpsWatch 화면은 **운영 관리** 탭에서 접근

학습자는 가능하면 이 README의 계정 표를 보지 말고 `/staff/`부터 시작해도 됩니다.

## 시나리오

1. 로그인에 반복 시도 제한이 없고, 약한 실습 비밀번호(`maint123`)를 허용한다.
2. 로그인 사용자에게 제공되는 정상 에이전트 상태 API 응답 JSON에 고정된 가짜 내부 토큰이 평문으로 포함된다.
3. `maint`의 로그인 세션과 `inventory.run_diagnostics` 권한, 노출된 토큰을 함께 사용해 `/api/internal/diagnose/`를 호출한다. 토큰만으로는 실행할 수 없다.
4. 기존 호스트 진단 화면에 `;`/`&&`를 포함한 입력을 넣어 컨테이너 내부의 실제 명령 실행을 확인한다.
5. 시연한 코드의 인증·비밀번호·토큰·입력 검증 문제와 대응 방안을 설명한다. 방어 대책은 [`docs/SECURE_CODING.md`](docs/SECURE_CODING.md)에 정리되어 있다.

별도 발표 화면이나 취약/안전 모드 전환은 없습니다. 기존 화면에서 직접 입력하며 진행하는 순서는 [`docs/WALKTHROUGH.md`](docs/WALKTHROUGH.md)입니다.

## MTV 구조

| 역할 | 위치 | 책임 |
| --- | --- | --- |
| Model | `inventory/models.py` | 직원, 서버, 점검 기록 |
| Template | `inventory/templates/inventory/` | 로그인, 직원 안내, 대시보드, 지원, 진단, 에이전트 |
| View | `inventory/views.py` | 요청, 인증 확인, 렌더링, JSON |
| URLconf | `opswatch/urls.py`, `inventory/urls.py` | 페이지·API 경로 |
| Service | `inventory/services/diagnostics.py` | 컨테이너 전용 실제 셸 실행과 호스트 보고서 |
| Management | `inventory/management/commands/seed_lab.py` | 멱등 시드 |
| Intranet | `intranet/` | 부대 업무 모델·폼·뷰·공통 디자인 템플릿 |
| Import | `intranet/management/commands/import_intranet.py` | 원본 SQLite 데이터의 멱등 이관 |

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
- 호스트에서 Django를 직접 띄우면 실제 셸 진단은 차단

컨테이너 격리는 커널 네임스페이스 수준입니다. 호스트 탈출·도커 소켓 실습은 이 프로젝트의 범위가 아닙니다. **가능하면 별도 실습 VM에서 실행하세요.**

## 설치와 실행

요구: Docker Compose v2, 로컬 전용.

```powershell
cd C:\Users\USER\Documents\opswatch
docker compose up --build
```

브라우저: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

MySQL이 healthy가 된 뒤 엔트리포인트가 `migrate`, `seed_lab`, `import_intranet`을 실행합니다. 로그인 후 `/`의 인트라넷 홈으로 이동합니다. 공개 당직 연락망은 `/staff/`에서 계속 이용할 수 있습니다.

### 통합 화면과 기존 데이터

- **인트라넷**: 홈, 공지사항, 게시판(검색·분류·댓글), 결재(받은 문서·내 기안), 일정(공통·개인), 부대원, 내 정보·비밀번호 변경.
- **운영 관리**: 기존 운영 개요(`/dashboard/`), 당직 연락망, 내부 토큰, 호스트 진단, 상황실 에이전트. 인트라넷과 같은 Django 로그인 세션·메뉴·색상·컴포넌트를 사용합니다.
- `파이선/app.py`의 기능을 Django `intranet` 앱으로 옮겼습니다. 별도 Python 서버나 iframe은 사용하지 않습니다. 원본 소스와 `파이선/intranet.db`는 보존하고, 통합 후 변경 사항은 Django DB에 저장합니다.
- 최초 이관 대상: 원본 계정 12개, 공지 5개, 게시글 12개, 댓글 7개, 결재 7개, 일정 8개. 원본 DB의 `정보공유` 분류와 `지출결의`·`품의` 문서 종류도 그대로 지원합니다.
- 이관을 다시 실행해도 통합 후 수정한 내용·비밀번호를 덮어쓰거나 삭제한 문서를 복원하지 않습니다. 기존 Django 계정과 ID가 같으면 기존 계정과 프로필을 유지합니다. 원본 로그인 세션은 가져오지 않으며, 원본 계정의 비밀번호 해시는 최초 정상 인증 시 Django 형식으로 자동 갱신됩니다.
- 인트라넷 관리자는 공지 작성·삭제와 공통 일정 등록이 가능합니다. 일반 사용자는 본인 게시글·일정만 삭제하고, 결재는 기안자·지정 결재자·인트라넷 관리자만 열람합니다. 승인·반려는 지정 결재자만 한 번 처리할 수 있습니다. 인트라넷 관리자 역할은 Django 관리자 권한이나 호스트 진단 권한을 부여하지 않습니다.
- `파이선/military_intranet_lab/`는 별도의 이전 실습 자료로 보존합니다. 해당 서버를 함께 실행할 필요는 없습니다.

원본 데이터를 수동 이관하려면:

```powershell
.\.venv\Scripts\python manage.py import_intranet
# 다른 원본 파일을 명시하려면: --source "경로\intranet.db"
```

이관 ID 매핑은 한 원본 DB 기준입니다. 다른 ID 체계의 DB를 같은 대상 DB에 추가 병합하는 용도로 사용하지 마세요.

### 운영 개요의 실습 데이터

- 에이전트 CPU·메모리는 `seed_metrics=True`인 실습 호스트만 브라우저에서 3초마다 변동합니다. 실제 호스트/컨테이너 사용률을 수집하지 않으며 DB의 원본 값과 호스트 상태는 바꾸지 않습니다.
- 탭이 숨겨지면 갱신을 멈추고, 다시 열면 재개합니다. JavaScript를 끄면 저장된 최초 값만 표시합니다. `seed_metrics=False`인 호스트는 항상 저장된 값을 표시합니다.
- 알림 추이는 정보·주의·위험별 **12시간 시뮬레이션 예시**입니다. 시간별 건수와 피크는 실제 점검 기록과 무관합니다. 상단의 최근 점검 건수·통과/실패 및 하단 점검 표는 DB 기록입니다.
- 화면 변경을 실행 중인 Docker 환경에 반영하려면 `docker compose up -d --build web`을 실행한 뒤 기존 화면을 새로고침합니다.

### 호스트에서 단위 테스트/화면만

호스트에서는 화면 확인만 가능하며 셸 진단은 차단됩니다. 실제 명령 삽입 시연은 Docker Compose로 실행하세요.

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
$env:OPSWATCH_DATABASE = "sqlite"
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py seed_lab
.\.venv\Scripts\python manage.py import_intranet
.\.venv\Scripts\python manage.py runserver 127.0.0.1:8000
```

## 실습 계정 (가짜)

운영자용입니다. 기존 로그인 화면에서 `maint` / `maint123` 로그인을 시연합니다.

| 담당자 | 부서 | 로그인 ID | 비밀번호 |
| --- | --- | --- | --- |
| 박도윤 | 망당직 · 유지보수 | `maint` | `maint123` |
| 김서연 | 인력관리 | `seoyeon` | `seoyeon123` |
| 이민준 | 체계운영 | `minjun` | `minjun123` |
| 최하린 | 상황실 | `harin` | `harin123` |

기본 시드에서 `maint`만 Django 권한 `inventory.run_diagnostics`를 직접 부여받습니다. `seoyeon`, `minjun`, `harin`은 진단·에이전트 실행 권한이 없습니다. 모두 관리자(`is_staff`, `is_superuser`) 권한은 없습니다. 비밀번호는 의도적으로 약하며 DB에는 Django 해시로 저장합니다. `seed_lab` 재실행 시 위 계정을 생성·갱신하고 비밀번호를 위 값으로 초기화하며, `maint`에는 진단 직접 권한을 부여하고 나머지 기본 계정에서는 해당 직접 권한을 제거합니다. 당직 연락망에는 로그인 ID만 표시합니다.

원본 인트라넷 계정도 같은 로그인 화면을 사용합니다. 현재 원본 데이터의 관리자는 `admin` / `admin1234`, 일반 계정 예시는 `jykim` / `nova1234`입니다. 이관 계정에는 기본적으로 진단 권한이 없으며, `admin`의 부대 업무 관리용 역할도 진단 권한이나 Django 관리자 권한과 별개입니다. 이관 후 변경한 비밀번호는 `import_intranet` 재실행으로 초기화되지 않습니다.

- 취약 내부 토큰: 로그인 사용자에게 제공되는 **내부 토큰** 화면의 **에이전트 상태 조회**가 호출하는 `GET /api/internal/metadata/` 응답 JSON에 평문 포함. 화면에는 서비스명과 상태만 표시
- 상태 조회는 현재 세션에 토큰을 저장합니다. 진단·에이전트 메뉴는 `inventory.run_diagnostics` 권한이 있을 때만 표시되며, 일반 계정은 토큰을 받아도 실행할 수 없습니다. 로그아웃하면 다시 조회해야 합니다.
- 진단·에이전트 페이지는 비로그인 시 로그인으로 이동하고, 로그인했지만 권한이 없으면 403입니다. 두 실행 API는 로그인 세션(없으면 401), 진단 권한(없으면 403), 기존 토큰 검사를 순서대로 요구합니다.
- 두 실행 API의 CSRF 면제(`csrf_exempt`)와 교육용 고정 토큰 노출·셸 명령 삽입 취약점은 유지됩니다. 권한 구분은 이 취약점들을 제거한 것이 아닙니다.
- FLAG: 컨테이너 `/opt/challenge/flag.txt`의 실제 실습 파일 (`challenge/flag.txt`에서 이미지에 복사)

## 변경사항

- 호스트 진단·상황실 에이전트 실행을 Django의 `inventory.run_diagnostics` 권한으로 분리했습니다. 기본 시드는 `maint`만 허용하며, 다른 시드·이관 계정과 인트라넷 관리자 역할은 기본적으로 허용하지 않습니다.
- 화면과 API 모두 로그인·권한을 요구하도록 변경했습니다. 고정 토큰만으로 세션 없이 실행하던 경로는 더 이상 허용하지 않습니다. 로그인 사용자 대상 메타데이터 토큰 노출, API CSRF 면제, 셸 명령 삽입은 교육 목적으로 유지합니다.

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

삭제하지 않는 것: 호스트의 이 소스 트리, Docker 엔진 자체.

호스트 SQLite를 썼다면 `db.sqlite3`를 지운 뒤 `migrate` + `seed_lab`을 다시 실행합니다.

## 테스트

```powershell
$env:OPSWATCH_DATABASE = "sqlite"
.\.venv\Scripts\python manage.py check
.\.venv\Scripts\python manage.py makemigrations --check --dry-run
.\.venv\Scripts\python manage.py test
```

호스트 단위 테스트는 `subprocess`를 모의하고 런타임 차단·입력 오류·출력 상한·타임아웃을 확인합니다. 실제 셸 동작은 격리된 컨테이너의 기존 진단·에이전트 화면에서 확인합니다.

## 안전 주의

- `127.0.0.1` 외 바인딩, ngrok/cloudflared 등 터널, 공인 NIC 배포 금지
- 실제 비밀번호·토큰·사내 호스트를 넣지 말 것
- 이 코드의 취약 인증·토큰 설계를 다른 시스템에 복사하지 말 것
- 개선 방법은 [`docs/SECURE_CODING.md`](docs/SECURE_CODING.md)
