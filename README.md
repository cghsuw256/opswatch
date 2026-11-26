# 국방망 인트라넷

로컬 교육 환경입니다. 신규 시스템으로 이관한 뒤 담당자가 구형 홈페이지를 종료하지 않아, 실습 대상은 남아 있는 레거시 사이트입니다. 실제 국방망이나 외부 시스템에는 배포하지 않습니다.

| 구분 | 접속 주소 | 데이터 |
| --- | --- | --- |
| 신규 국방망 인트라넷 | [http://intranet.localhost:8001/](http://intranet.localhost:8001/) | 독립 SQLite 볼륨, 신규 발급 계정 |
| 레거시 실습 사이트 | [http://127.0.0.1:8000/](http://127.0.0.1:8000/) | 기존 MySQL 볼륨, 실습 계정 |

### 신규 시스템 실행과 계정 발급

```powershell
docker compose -f docker-compose.patched.yml up -d --build --wait
docker compose -f docker-compose.patched.yml exec web python manage.py create_operator duty01 --name "김준호" --rank "중사" --diagnostics
docker compose -f docker-compose.patched.yml exec web python manage.py create_operator support01 --name "박서윤" --rank "7급 군무원"
```

- 비밀번호는 터미널 프롬프트에서 두 번 입력합니다. 초기 계정이나 레거시 계정·데이터 자동 이관은 없습니다. 포털 관리 역할은 `--portal-admin`, 호스트 점검 기록 조회 권한은 `--diagnostics`로 각각 부여합니다.
- [군인사법 제3조](https://www.law.go.kr/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1029126493)의 군인 계급과 [군무원인사법 제3조](https://www.law.go.kr/LSW/lsLawLinkInfo.do?lsJoLnkSeq=900324816&chrClsCd=010202)의 일반군무원 1~9급을 사용합니다. 홈, 부대원, 내 정보, 결재선, 당직 연락망에서 계급·직급을 표시합니다.
- 공지사항·게시판·결재·일정 등 기존 업무 화면은 유지합니다. 공개 연락망에서 콘솔 ID를 빼고, 개발 설정·내부 토큰·기존 실행 API와 에이전트는 신규 사이트에 연결하지 않습니다. 서비스 상태와 호스트 진단은 DB에 저장된 상태·기록만 조회합니다.
- `/dev/setting`은 등록하지 않습니다. 레거시 `/admin/setting`은 기존 데모 JSON을 표시합니다. 신규 `/admin/setting`은 포털 관리자에게 DB 엔진 종류만 표시합니다.
- 신규 로그인은 출발지당 60초 구간에 최대 10회, 비밀번호는 최소 14자와 Django 검증 정책을 적용합니다. 신규 사이트 주소는 `intranet.localhost`를 사용하세요. 별도 호스트와 쿠키, 별도 DB·서명 키를 사용하며 둘 다 로컬에만 바인딩합니다.

레거시 진행 자료: [`docs/WALKTHROUGH.md`](docs/WALKTHROUGH.md). 신규·레거시 방어 비교: [`docs/SECURE_CODING.md`](docs/SECURE_CODING.md).

## 폴더 구조

| 위치 | 역할 |
| --- | --- |
| `app/` | Django 실행 파일과 Python 의존성 |
| `app/config/` | 공통 Django 설정, 레거시·신규별 설정과 루트 URL, WSGI |
| `app/unit_portal/` | 부대 업무 앱 |
| `app/operations/` | 운영 관리 앱과 실습 시드 |
| `app/patched_portal/` | 신규 로그인 정책, 계급·직급, 안전한 운영 화면 |
| `docker/` | Dockerfile, 시작 스크립트, 컨테이너 실습 리소스 |
| `docs/` | 실습 절차와 보안 개선안 |

Django 앱 레이블 `intranet`, `inventory`는 유지하므로 기존 DB 테이블과 권한을 그대로 사용합니다.

Django 관리자 사이트는 연결하지 않습니다. `/admin/diagnostics/`는 같은 경로를 사용하지만, 신규에서는 저장된 점검 기록만 조회합니다.

## 레거시 실습 환경 격리

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

## 레거시 설치와 실행

요구: Docker Compose v2, 로컬 전용.

```powershell
# 저장소 루트에서 실행
docker compose up --build
```

브라우저: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

MySQL이 healthy가 된 뒤 엔트리포인트가 `migrate`와 `seed_lab`을 실행합니다. 로그인 후 `/`의 인트라넷 홈으로 이동합니다. 공개 당직 연락망은 `/staff/`에서 계속 이용할 수 있습니다.

기존 MySQL 볼륨을 재사용하기 위해 Compose 내부 프로젝트 ID(`opswatch-lab`)는 유지합니다.

기존 DB에 마이그레이션을 적용하면 사용하지 않는 이관 ID 매핑 테이블만 삭제됩니다. 이관된 계정·게시물과 기존 로그인 호환성은 유지됩니다.

### 통합 화면

- **인트라넷**: 홈, 공지사항, 게시판(검색·분류·댓글), 결재(받은 문서·내 기안), 일정(공통·개인), 부대원, 내 정보·비밀번호 변경.
- **운영 관리**: 기존 운영 개요(`/dashboard/`), 당직 연락망, 내부 토큰, 호스트 진단, 상황실 에이전트. 인트라넷과 같은 Django 로그인 세션·메뉴·색상·컴포넌트를 사용합니다.
- 인트라넷 관리자는 공지 작성·삭제와 공통 일정 등록이 가능합니다. 일반 사용자는 본인 게시글·일정만 삭제하고, 결재는 기안자·지정 결재자·인트라넷 관리자만 열람합니다. 승인·반려는 지정 결재자만 한 번 처리할 수 있습니다. 인트라넷 관리자 역할은 Django 관리자 권한이나 호스트 진단 권한을 부여하지 않습니다.

### 운영 개요의 실습 데이터

- 에이전트 CPU·메모리는 `seed_metrics=True`인 실습 호스트만 브라우저에서 3초마다 변동합니다. 실제 호스트/컨테이너 사용률을 수집하지 않으며 DB의 원본 값과 호스트 상태는 바꾸지 않습니다.
- 탭이 숨겨지면 갱신을 멈추고, 다시 열면 재개합니다. JavaScript를 끄면 저장된 최초 값만 표시합니다. `seed_metrics=False`인 호스트는 항상 저장된 값을 표시합니다.
- 알림 추이는 정보·주의·위험별 **12시간 시뮬레이션 예시**입니다. 시간별 건수와 피크는 실제 점검 기록과 무관합니다. 상단의 최근 점검 건수·통과/실패 및 하단 점검 표는 DB 기록입니다.
- 화면 변경을 실행 중인 Docker 환경에 반영하려면 `docker compose up -d --build web`을 실행한 뒤 기존 화면을 새로고침합니다.

### 호스트에서 단위 테스트/화면만

호스트에서는 화면 확인만 가능하며 셸 진단은 차단됩니다. 실제 명령 삽입 시연은 Docker Compose로 실행하세요.

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r app/requirements.txt
$env:OPSWATCH_DATABASE = "sqlite"
.\.venv\Scripts\python app/manage.py migrate
.\.venv\Scripts\python app/manage.py seed_lab
.\.venv\Scripts\python app/manage.py runserver 127.0.0.1:8000
```

## 레거시 실습 계정 (가짜)

운영자용입니다. 기존 로그인 화면에서 `maint` / `maint123` 로그인을 시연합니다.

| 담당자 | 부서 | 로그인 ID | 비밀번호 |
| --- | --- | --- | --- |
| 박도윤 | 망당직 · 유지보수 | `maint` | `maint123` |
| 김서연 | 인력관리 | `seoyeon` | `seoyeon123` |
| 이민준 | 체계운영 | `minjun` | `minjun123` |
| 최하린 | 상황실 | `harin` | `harin123` |

기본 시드에서 `maint`만 Django 권한 `inventory.run_diagnostics`를 직접 부여받습니다. `seoyeon`, `minjun`, `harin`은 진단·에이전트 실행 권한이 없습니다. 모두 관리자(`is_staff`, `is_superuser`) 권한은 없습니다. 비밀번호는 의도적으로 약하며 DB에는 Django 해시로 저장합니다. `seed_lab` 재실행 시 위 계정을 생성·갱신하고 비밀번호를 위 값으로 초기화하며, `maint`에는 진단 직접 권한을 부여하고 나머지 기본 계정에서는 해당 직접 권한을 제거합니다. 당직 연락망에는 로그인 ID만 표시합니다.

- 취약 내부 토큰: 로그인 사용자에게 제공되는 **내부 토큰** 화면의 **에이전트 상태 조회**가 호출하는 `GET /api/internal/metadata/` 응답 JSON에 평문 포함. 화면에는 서비스명과 상태만 표시
- 상태 조회는 현재 세션에 토큰을 저장합니다. 진단·에이전트 메뉴는 `inventory.run_diagnostics` 권한이 있을 때만 표시되며, 일반 계정은 토큰을 받아도 실행할 수 없습니다. 로그아웃하면 다시 조회해야 합니다.
- 진단·에이전트 페이지는 비로그인 시 로그인으로 이동하고, 로그인했지만 권한이 없으면 403입니다. 두 실행 API는 로그인 세션(없으면 401), 진단 권한(없으면 403), 기존 토큰 검사를 순서대로 요구합니다.
- 두 실행 API의 CSRF 면제(`csrf_exempt`)와 교육용 고정 토큰 노출·셸 명령 삽입 취약점은 유지됩니다. 권한 구분은 이 취약점들을 제거한 것이 아닙니다.
- FLAG: 컨테이너 `/opt/challenge/flag.txt`의 실제 실습 파일 (`docker/challenge/flag.txt`에서 이미지에 복사)

## 변경사항

- 신규 국방망 인트라넷을 별도의 Compose 프로젝트로 분리했습니다. 레거시 경로와 데이터 볼륨은 그대로 유지합니다.

- 호스트 진단·상황실 에이전트 실행을 Django의 `inventory.run_diagnostics` 권한으로 분리했습니다. 기본 시드는 `maint`만 허용하며, 다른 시드·이관 계정과 인트라넷 관리자 역할은 기본적으로 허용하지 않습니다.
- 화면과 API 모두 로그인·권한을 요구하도록 변경했습니다. 고정 토큰만으로 세션 없이 실행하던 경로는 더 이상 허용하지 않습니다. 로그인 사용자 대상 메타데이터 토큰 노출, API CSRF 면제, 셸 명령 삽입은 교육 목적으로 유지합니다.

## 레거시 종료 · 재시작 · 초기화

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

신규 사이트 검증:

```powershell
docker compose -f docker-compose.patched.yml exec web python manage.py test patched_portal
docker compose -f docker-compose.patched.yml exec web python manage.py migrate --check
```

레거시 사이트 검증:

```powershell
$env:OPSWATCH_DATABASE = "sqlite"
.\.venv\Scripts\python app/manage.py check
.\.venv\Scripts\python app/manage.py makemigrations --check --dry-run
.\.venv\Scripts\python app/manage.py test unit_portal operations
```

호스트 단위 테스트는 `subprocess`를 모의하고 런타임 차단·입력 오류·출력 상한·타임아웃을 확인합니다. 실제 셸 동작은 격리된 컨테이너의 기존 진단·에이전트 화면에서 확인합니다.

## 안전 주의

- `127.0.0.1` 외 바인딩, ngrok/cloudflared 등 터널, 공인 NIC 배포 금지
- 실제 비밀번호·토큰·사내 호스트를 넣지 말 것
- 이 코드의 취약 인증·토큰 설계를 다른 시스템에 복사하지 말 것
- 개선 방법은 [`docs/SECURE_CODING.md`](docs/SECURE_CODING.md)
