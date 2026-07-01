TV 가격 트래킹 메일 자동화 V3

1. 운영 흐름
- GitHub Actions가 매일 오전 9시(KST)에 실행됩니다.
- TV 기본 모델 7개를 네이버 쇼핑 API로 조회합니다.
- 기준가 대비 저가/고가 통계, AI 요약, 최저가 게시물, TOP20 게시물을 정적 HTML로 생성합니다.
- 생성된 HTML, PNG 캡처, price_data XLSX를 메일에 첨부합니다.

2. GitHub Actions
- workflow 파일: .github/workflows/test_mail.yml
- 자동 실행: 매일 09:00 KST
- 수동 실행: GitHub Actions > Test Mail > Run workflow

3. 필수 Repository Secrets
- GMAIL_ID
- GMAIL_APP_PASSWORD
- NAVER_CLIENT_ID
- NAVER_CLIENT_SECRET

4. 관리 파일
- keyword_master.xlsx
  - TV 기본 모델과 기준가를 관리합니다.
  - GitHub 웹에서 직접 수정할 수 있습니다.

- exclusion_keywords.xlsx
  - 상품명 또는 판매처에 포함되면 제외할 키워드를 관리합니다.
  - 기본 제외 키워드: 렌탈, 약정, 호환, 구독, 전동, 보호기, 고정식, 이동식, 거치대

5. 수집 기준
- 당사 모델코드와 경쟁사 모델코드를 각각 최대 1000건까지 조회합니다.
- 네이버 API의 total 값은 전체 검색 결과 수입니다.
- 첨부되는 price_data는 실제 가져온 MAX 1000건 기준입니다.
- 기준가의 10% 미만 가격은 오류 가능성이 높아 제외합니다.

6. 로컬 테스트
  py -m pip install -r requirements.txt
  set GMAIL_ID=your_gmail@gmail.com
  set GMAIL_APP_PASSWORD=your_app_password
  set NAVER_CLIENT_ID=your_naver_client_id
  set NAVER_CLIENT_SECRET=your_naver_client_secret
  py create_tv_report.py
  py render_report_image.py
  py test_mail.py

7. 주요 소스
- create_tv_report.py: 네이버 API 조회, 데이터 가공, XLSX 생성
- report_generator.py: 정적 HTML 리포트 생성
- render_report_image.py: HTML 리포트 PNG 캡처 생성
- test_mail.py: 최신 리포트 조회 후 메일 발송
- storage.py: XLSX 마스터 파일과 수집 스냅샷 처리
