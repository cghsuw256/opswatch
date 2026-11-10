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

## 3. 지원 스크립트의 하드코딩 토큰

**원인:** `support_scripts/opswatch-healthcheck.sh` 에 내부 API 토큰이 평문으로 들어 있습니다.

**개선:**

- 토큰을 저장소·다운로드 파일에 넣지 않습니다.
- 배포 시 시크릿 매니저·환경 변수·짧은 TTL의 서비스 계정 토큰을 사용합니다.
- 지원 스크립트는 토큰 자리를 플레이스홀더로만 남깁니다.
- 유출 가정 하에 회전·감사 로그를 둡니다.

## 4. 세션 + 정적 토큰만으로 위험한 진단 API

**원인:** 로그인만 되면 고정 토큰으로 `/api/internal/diagnose/` 가 열립니다. 권한 구분과 만료가 없습니다.

**개선:**

- 진단은 별도 권한(staff flag, 그룹) 검사.
- 토큰은 HMAC 서명 + 만료, 또는 mTLS.
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
