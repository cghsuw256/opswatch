# OpsWatch

Python 3.14 / Django 5.2.19. SQLite만 사용합니다.

## 계정

- 관리자: `admin` / `1234`
- 구형 유지보수: `maint` / `maint123`

## 실행

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py runserver
```

`python manage.py runserver`는 구형 `8000`과 패치 `8001`을 함께 실행합니다. 데이터는 `db.sqlite3` 하나에 있습니다.

## 테스트 URL

- 구형 로그인: http://127.0.0.1:8000/login/
- 구형 당직 연락망: http://127.0.0.1:8000/staff/
- 구형 호스트 진단: http://127.0.0.1:8000/admin/diagnostics/
- 패치 로그인: http://127.0.0.1:8001/login/
- 패치 호스트 진단: http://127.0.0.1:8001/admin/diagnostics/

진단 화면에는 `db-01.lab.local`을 입력하면 등록 호스트 응답이 나옵니다. `127.0.0.1; cat /opt/challenge/unit_members.csv`를 입력하면 가상 부대원 명단이 표시됩니다.

### 같은 내부망에서 패치 사이트 열기

`ipconfig`에서 이 PC의 Wi-Fi 또는 이더넷 IPv4 주소를 확인한 뒤 실행하세요.

```powershell
python manage.py runserver --lan 192.168.25.55
```

주소는 실제 IPv4로 바꾸고, 다른 기기에서 `http://<IPv4>:8001/`을 엽니다. 레거시 사이트는 이 PC의 `127.0.0.1`에만 열립니다. 신뢰하는 내부망에서 테스트 계정만 사용하고 공유기 포트포워딩은 하지 마세요. Windows 방화벽에서 막히면 개인 네트워크의 로컬 서브넷에만 TCP `8001`을 허용하세요.

