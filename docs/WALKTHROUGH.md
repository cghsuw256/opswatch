# OpsWatch 실습 화면 발표 순서 (스포일러)

별도 발표 탭 없이 기존 화면에서 직접 입력하며 진행합니다. 대상은 `http://127.0.0.1:8000`의 격리된 로컬 실습 컨테이너뿐입니다. 계정·토큰·FLAG는 가짜이지만 셸과 파일 읽기는 컨테이너 안에서 실제로 실행됩니다.

## 1. 당직 연락망 → 로그인: 인증 시도와 약한 비밀번호

1. `/staff/`의 유지보수 담당자에서 콘솔 ID `maint`를 확인합니다.
2. 기존 `/login/` 화면에서 `maint`와 잘못된 비밀번호를 여러 번 입력합니다. 실패 화면은 HTTP 200으로 다시 표시되고, 잠금·CAPTCHA·추가 지연은 없습니다. 비밀번호 해시 검증에 걸리는 시간은 발생합니다.
3. `maint` / `maint123`으로 로그인합니다. 반복 실패 후에도 `/dashboard/`로 이동합니다.
4. 소스의 `login_view()`와 `AUTH_PASSWORD_VALIDATORS = []`, 시드의 약한 초기 비밀번호를 근거로 원인을 설명합니다. `1234`, `admin123`은 약한 비밀번호의 설명 예시이며 실제 시드 계정 비밀번호는 아닙니다.

## 2. 내부 토큰: 정상 상태 응답에 숨은 고정 토큰

1. 기존 **내부 토큰** 메뉴(`/support/`)를 엽니다.
2. 개발자 도구 Network 또는 프록시 기록을 연 상태에서 **에이전트 상태 조회**를 누릅니다.
3. 화면에는 서비스 `opswatch-agent`와 상태 `ok`만 표시됩니다.
4. `GET /api/internal/metadata/`의 응답 JSON에서 `metadata.internal_token`을 확인합니다.

```json
{"service":"opswatch-agent","status":"ok","metadata":{"internal_token":"ow-lab-internal-9f3c2a1b7e44","authentication":"static-token","expires_in":null}}
```

상태 조회는 현재 Django 세션에 토큰을 저장하여 진단·에이전트 화면을 활성화합니다. 별도 토큰 발급 동작은 없습니다. 모든 계정이 같은 고정값을 받으며 만료되지 않습니다.

## 3. 호스트 진단: 노출된 토큰과 실제 셸 실행

기존 **호스트 진단** 메뉴(`/admin/diagnostics/`)의 진단 대상에 직접 입력합니다.

### 정상 입력

```text
web-01.lab.local
```

저장된 상태·점검 기록과 실제 `getent hosts` 출력이 함께 표시됩니다. 이 조회는 ping이 아니라 호스트 주소 조회입니다.

### 명령 삽입 입력

```text
web-01.lab.local; whoami
```

출력의 `appuser`는 실제 컨테이너 실행 계정입니다.

```text
web-01.lab.local && cat /opt/challenge/flag.txt
```

실제 컨테이너 파일을 읽은 결과는 `FLAG{S3CuR3_C0DiNg}`입니다. `&&`는 선행 명령이 성공해야 뒤 명령을 실행하고, `;`는 성공 여부와 관계없이 다음 명령을 실행합니다.

취약 지점은 `inventory/services/diagnostics.py`입니다.

```python
subprocess.run(
    f"/usr/bin/getent hosts {cleaned}",
    shell=True, capture_output=True, text=True, timeout=3,
)
```

명령 입력은 실제 셸에 전달됩니다. 호스트 실행은 차단되며, 격리 컨테이너에서도 3초·출력 8KiB·동시 1개 제한이 적용됩니다. 결과는 `textContent`로 표시합니다.

### 세션 없이 토큰 재사용

프록시에서 위 `POST /api/internal/diagnose/` 요청을 Repeater로 보냅니다. `Cookie`와 `X-CSRFToken`을 제거하고 `X-OpsWatch-Token`만 유지하면 계속 호출할 수 있습니다. 토큰까지 제거하면 403입니다.

기존 화면은 로그인·상태 조회를 요구하지만 API는 고정 토큰만 검사한다는 차이를 설명합니다. 실제 국방망·외부 서버에는 이 요청을 보내지 마세요.

### 상황실 에이전트에서도 같은 경로

기존 **상황실 에이전트** 메뉴(`/ops/assistant/`)에서 요청 내용에 호스트 상태 확인을 입력하고, 대상에 다음을 입력합니다.

```text
web-01.lab.local; id
```

실제 `uid=1000(appuser)` 출력이 응답에 포함됩니다. 에이전트가 명령을 별도로 만드는 것이 아니라 같은 진단 서비스에 대상 문자열을 전달합니다. API `/api/internal/assistant/`도 같은 정적 토큰만 신뢰합니다.

## 4. 시연한 코드에서 대응 방안 설명

화면·소스·네트워크 응답을 근거로 다음을 정리합니다. 실습 중 취약 기능을 없애는 별도 모드 전환은 없습니다.

- 인증: 실패 횟수 제한, 잠금·점진적 지연, MFA, 초기 비밀번호 변경 강제
- 비밀번호: 설정·변경 시 길이·흔한 비밀번호·계정 유사성 검증
- 토큰: 정상 응답에서 공유 비밀 제거, 유출 토큰 폐기·회전, 세션·사용자별 권한 확인
- 진단: 셸 문자열 결합 제거, 안전한 라이브러리와 등록 호스트 허용 목록 사용

상세 개선안: [`SECURE_CODING.md`](SECURE_CODING.md).
