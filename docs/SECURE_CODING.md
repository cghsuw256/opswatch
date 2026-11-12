# 취약점 원인과 개선

이 문서는 OpsWatch 랩의 의도적 약점을 **고치는 방법**만 설명합니다.  
랩 코드에 아래 패치를 적용하면 실습 시나리오가 깨집니다.

## 1. 직원 안내에서 콘솔 ID 노출

**원인:** 인증 없는 `/staff/` 가 유지보수 로그인 ID를 그대로 렌더링합니다.  
`inventory/templates/inventory/staff.html`, 시드의 `Employee.login_id`.

**개선:**

- 공개 게시판에는 이름·내선만 두고 로그인 ID는 내부 IAM에만 둡니다.
- 필요하면 인증된 인사 담당자 뷰로 분리합니다.

## 2. 약한 비밀번호와 잠금 없음

**원인:** `AUTH_PASSWORD_VALIDATORS = []`, 시드 비밀번호 `maint123`, 로그인 뷰에 실패 횟수 제한이 없습니다.

**개선:**

- Django 기본 `AUTH_PASSWORD_VALIDATORS` 를 켜고 길이·복잡도를 강제합니다.
- `django-axes` 또는 캐시 카운터로 실패 N회 후 잠금·지연을 넣습니다.
- 초기 비밀번호는 일회용으로 발급하고 재설정을 강제합니다.
- 가능하면 SSO/패스키를 사용합니다.

## 3. 고정 토큰을 발급처럼 반환

**원인:** `/api/internal/token/` 이 인증된 사용자에게 `settings.OPSWATCH_INTERNAL_TOKEN` 고정값을 그대로 줍니다. 만료·회전·사용자 바인딩이 없습니다.

**개선:**

- 토큰은 시크릿 매니저에서 발급하고 짧은 TTL·audience를 넣습니다.
- 사용자·세션에 바인딩하고 재사용을 감사합니다.
- 브라우저에 장기 내부 토큰을 보여 주지 않습니다.
- 진단 API는 서버 세션·권한만으로 인가하는 편이 낫습니다.

## 4. 정적 토큰만으로 진단 API가 열림

**원인:** `/api/internal/diagnose/` 가 세션·CSRF를 보지 않고 고정 토큰만 확인합니다. 토큰이 유출되면 로그인 없이 명령 실행 경로가 열립니다.

**개선:**

- 진단 API는 서버 세션과 별도 권한(staff, 그룹)을 함께 검사합니다.
- CSRF를 유지하거나 mTLS·짧은 TTL 서명 토큰을 씁니다.
- 고정 공유 시크릿으로 관리 동작을 인가하지 않습니다.
- 관리 동작은 감사 로그와 2차 확인.

## 5. 셸 문자열 결합 (Command Injection)

**원인:** `inventory/services/diagnostics.py`

```python
command = f"/usr/bin/getent hosts {target}"
subprocess.run(command, shell=True, ...)
```

사용자 입력이 셸 메타문자(`;`, `|`, `$()`, 백틱 등)로 추가 명령을 만듭니다.

**개선 (필수):**

1. `shell=False` 로 인자 리스트만 전달합니다.

```python
subprocess.run(
    ["/usr/bin/getent", "hosts", target],
    shell=False,
    check=False,
    capture_output=True,
    timeout=3,
)
```

2. 진단 대상을 허용 목록으로만 받습니다. 예: `Server.hostname` 쿼리 결과와 일치하는 값만.
3. 호스트명 정규식(`^[a-z0-9.-]+$`)을 통과해도 허용 목록이 없으면 거절합니다.
4. 컨테이너에서도 이 API를 기본 비활성화하고, 별도 읽기 전용 진단 바이너리를 둡니다.
5. 타임아웃·출력 상한·동시성 제한은 유지하되, 취약점의 대체가 아닙니다.

## 6. 출력 XSS

랩은 JSON → `textContent` 로 결과를 넣습니다. 이 부분은 유지하세요.  
`innerHTML` 이나 `|safe` 로 진단 출력을 넣지 마세요.

## 체크리스트

- [ ] 강한 비밀번호 정책
- [ ] 로그인 시도 제한
- [ ] 비밀정보는 코드·정적 파일 밖
- [ ] 셸 사용 금지, 인자 분리 실행
- [ ] 허용된 진단 대상만 실행
- [ ] 관리 API와 Django Admin 권한 분리
- [ ] 로컬 바인딩·비특권 컨테이너는 방어 계층이지 앱 버그의 면책이 아님
