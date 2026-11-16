# OpsWatch 풀이 (스포일러)

대상은 이 저장소의 **가상 국방망 인트라넷 교육 복제**만입니다.

- 베이스 URL: `http://127.0.0.1:8000`
- 모든 계정·토큰·FLAG는 가짜입니다.
- 실제 국방망, 다른 호스트, 공인 주소에 같은 요청을 보내지 마세요.

## 1. 유지보수 ID

브라우저에서 `http://127.0.0.1:8000/staff/` 를 엽니다. 인증이 없습니다.

야간유지보수 담당 박도윤의 **콘솔 ID**가 `maint` 로 나옵니다.

## 2. 약한 비밀번호

`http://127.0.0.1:8000/login/` 에서 ID `maint` 와 흔한 실습 비밀번호를 시도합니다.  
이 랩의 값은 `maint123` 입니다. 실패해도 계정이 잠기지 않습니다.

로그인 후 `/dashboard/` 에서 시드된 CPU·메모리 카드를 볼 수 있습니다.

## 3. 고정 토큰 발급

화면: `http://127.0.0.1:8000/support/`

**토큰 발급**을 누르면 화면에는 `발급 완료`만 표시됩니다. 토큰 값은 화면에 나오지 않고, 같은 요청의 JSON 응답에만 있습니다. 사용자별 발급·만료가 아니라 항상 같은 값입니다.

발급 전 호스트 진단 화면의 입력·실행 버튼은 비활성화됩니다. 발급 시 서버의 Django 세션에 토큰이 저장되고, 이후 진단 화면으로 이동하거나 새로고침하면 활성화됩니다. 진단 실행 시 자동으로 토큰을 발급받지는 않습니다.

로그아웃 후 다시 로그인하면 화면은 다시 비활성화됩니다. 이는 정상 UI의 활성화 절차일 뿐, 진단 API의 인가 강화가 아닙니다. 이전에 확보한 고정 토큰은 계속 유효합니다.

```
GET http://127.0.0.1:8000/api/internal/token/
```

```
{"token": "ow-lab-internal-9f3c2a1b7e44", "token_type": "internal", "expires_in": null}
```

이 토큰만 있으면 로그인 세션 없이 진단 API를 호출할 수 있습니다.

## 4. 토큰만으로 진단 API 호출

화면 `http://127.0.0.1:8000/admin/diagnostics/` 는 로그인이 필요합니다.  
API `POST /api/internal/diagnose/` 는 세션·CSRF 없이 헤더 토큰만 검사합니다.

- 헤더: `X-OpsWatch-Token: ow-lab-internal-9f3c2a1b7e44`
- 쿠키 없음, CSRF 없음

토큰이 없으면 403입니다.

### Burp Suite 발표 순서

1. 로컬 실습 브라우저의 요청을 Burp Suite로 프록시하고 로그인합니다.
2. `/admin/diagnostics/`에서 발급 전 입력·실행 버튼이 비활성화된 상태를 보여 줍니다.
3. `/support/`에서 **토큰 발급**을 누릅니다. Proxy HTTP history에서 `GET /api/internal/token/` 응답의 고정 `token` 값을 확인합니다.
4. 호스트 진단으로 이동해 `web-01.lab.local`을 진단합니다. `POST /api/internal/diagnose/` 요청을 **Send to Repeater**로 보냅니다. 진단 과정에는 토큰 자동 발급 요청이 없습니다.
5. 로그아웃 후 다시 로그인해 화면이 다시 비활성화되는 것을 보여 줍니다.
6. Repeater 요청에서 `Cookie`와 `X-CSRFToken` 헤더를 제거하고, 확보한 `X-OpsWatch-Token`과 기존 JSON 본문만 유지해 전송합니다. 정상 진단 응답 `200`으로 세션 없는 재사용을 보여 줍니다.
7. 토큰 헤더까지 제거하면 `403`입니다. 아래 5단계의 입력을 같은 로컬 컨테이너 요청에 적용하면 명령어 삽입 경로도 관찰할 수 있습니다.

화면의 활성화 상태와 달리 API는 고정 토큰만 신뢰합니다. 토큰은 `docker-compose.yml`의 환경변수와 `opswatch/settings.py`의 기본값에 고정되어 있어 재발급해도 동일합니다.

## 4-1. 같은 토큰으로 상황실 에이전트 호출

화면 `http://127.0.0.1:8000/ops/assistant/` 도 로그인과 토큰 발급 뒤에만 입력할 수 있습니다.  
`POST /api/internal/assistant/` 는 세션을 보지 않고 진단 API와 같은 고정 토큰만 확인합니다. 대상 문자열은 가공하지 않고 `run_ping_diagnosis()`에 넘깁니다.

Burp Repeater에서는 진단 요청과 같이 쿠키를 제거하고 `X-OpsWatch-Token`만 남깁니다. 본문 예:

```json
{"message": "이름 해석 확인", "target": "web-01.lab.local"}
```

명령 결합 지점은 에이전트가 아니라 5단계의 진단 서비스입니다. 에이전트 응답에는 토큰 값을 넣지 않습니다.


정상 진단은 이름 해석이 아닙니다. `web-01.lab.local`을 넣으면 저장된 상태, CPU·메모리 점유율, 최근 점검 로그가 표시됩니다. 웹 프론트는 정상, CPU 23%, 메모리 41%입니다.

호스트에서 Django를 직접 실행 중이면 셸이 꺼져 403이 납니다. Compose로 띄운 뒤에만 5단계가 됩니다.

## 5. 명령 결합으로 FLAG 읽기

의도적 취약점 위치: `inventory/services/diagnostics.py` 의 `build_lab_command()`.

```python
return f"/usr/bin/getent hosts {target}"
```

이 문자열이 `subprocess.run(..., shell=True)` 로 실행됩니다.

진단 대상 입력 예 (이 랩의 localhost 컨테이너 전용):

```
web-01.lab.local; cat /opt/challenge/flag.txt
```

결과는 HTML로 삽입되지 않고 `<pre>` 의 `textContent` 로만 표시됩니다.  
성공 시 출력에 다음 가짜 FLAG가 포함됩니다.

```
FLAG{OPSWATCH_LAB_CMDI_LOCAL_ONLY}
```

세션 없이 토큰만으로 호출하는 예입니다. `127.0.0.1` 전용입니다.

```powershell
curl.exe -s -X POST "http://127.0.0.1:8000/api/internal/diagnose/" `
  -H "Content-Type: application/json" `
  -H "X-OpsWatch-Token: ow-lab-internal-9f3c2a1b7e44" `
  --data "{\"target\":\"web-01.lab.local; cat /opt/challenge/flag.txt\"}"
```
