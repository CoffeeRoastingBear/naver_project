네이버 API 기반 로컬 가격 트래킹 대시보드

1. 실행
- 개발 실행:
  py dashboard_app.py

- 실행 후 브라우저가 자동으로 열립니다.
  http://127.0.0.1:8765/

2. 최초 설정
- 화면 왼쪽의 "API Key 설정" 버튼을 누릅니다.
- 네이버 개발자 센터에서 발급받은 Client ID / Client Secret을 입력합니다.
- 저장된 값은 이 폴더의 config.json에만 보관됩니다.
- config.json은 간단한 난독화만 적용되어 있습니다. 외부 공유 금지입니다.

3. 데이터 저장
- DB는 사용하지 않습니다.
- 수집 데이터는 data/카테고리/키워드/YYYYMMDD_HHMMSS.t1 구조로 저장됩니다.
- .t1 내부 포맷은 utf-8-sig CSV입니다.
- 키워드 마스터는 keyword_master.t1에 저장됩니다.

4. 쿨타임
- 동일 카테고리 + 동일 키워드는 기본 30분에 1회만 네이버 API를 호출합니다.
- 30분 이내 재조회 시 최신 .t1 파일을 읽어 화면에 표시합니다.

5. 수집 제한
- 기본 수집 개수는 Top 100입니다.
- 옵션에서 Top 300까지 선택할 수 있습니다.
- 한 번에 최대 10개 키워드까지만 조회합니다.

6. exe 빌드
- Python이 설치된 개발 PC에서 아래 명령을 실행합니다.
  py -m pip install -r requirements.txt
  .\build_exe.ps1

- 빌드가 끝나면 dist/dashboard_tool.zip 파일이 생성됩니다.
- 최종 사용자에게는 dashboard_tool.zip만 전달하면 됩니다.

7. 배포 zip 구조
dashboard_tool.zip
  dashboard.exe
  README.txt
  config_sample.json
  data/

8. 메일 자동화 테스트
- 운영 스케줄링은 적용하지 않습니다.
- 테스트 메일은 수동 실행만 지원합니다.
- 메일 발송 스크립트는 네이버 API를 호출하지 않습니다.
- 메일 발송 스크립트는 get_latest_report()로 최신 HTML 리포트만 조회해 첨부합니다.
- TV 리포트 생성 스크립트가 네이버 API를 호출해 TV 기본 7개 모델 기준 정적 HTML을 생성합니다.

로컬 테스트:
  set GMAIL_ID=your_gmail@gmail.com
  set GMAIL_APP_PASSWORD=your_app_password
  set NAVER_CLIENT_ID=your_naver_client_id
  set NAVER_CLIENT_SECRET=your_naver_client_secret
  python create_tv_report.py
  python test_mail.py

GitHub Actions 테스트:
  1. GitHub Repository Secret에 GMAIL_ID, GMAIL_APP_PASSWORD, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET이 등록되어 있는지 확인합니다.
  2. GitHub Actions 메뉴에서 "Test Mail" workflow를 선택합니다.
  3. Run workflow 버튼으로 수동 실행합니다.
  4. workflow가 네이버 API로 TV 기본 7개 모델을 조회하고 HTML 리포트를 생성합니다.
  5. seongjin.son@samsung.com 메일 수신 여부와 HTML 첨부파일을 확인합니다.

테스트 메일 제목:
  [TEST] TV 가격 트래킹 리포트
