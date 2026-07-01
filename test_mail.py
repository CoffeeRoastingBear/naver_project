import os
import smtplib
import ssl
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from report_generator import get_latest_report


SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SENDER_ENV = "GMAIL_ID"
PASSWORD_ENV = "GMAIL_APP_PASSWORD"
RECIPIENT = "seongjin.son@samsung.com"
SUBJECT = "[TEST] 가격 트래킹 메일 자동화 테스트"


def current_environment():
    return "GitHub Actions" if os.getenv("GITHUB_ACTIONS") == "true" else "Local"


def build_html_body(sent_at, environment, report_path):
    report_name = Path(report_path).name if report_path else "-"
    return f"""<!DOCTYPE html>
<html lang="ko">
<body>
  <h2>메일 자동화 테스트</h2>
  <p>GitHub Actions 기반 메일 발송 테스트입니다.</p>
  <p>최신 HTML 가격 리포트를 첨부했습니다.</p>
  <ul>
    <li>발송 시간 : {sent_at}</li>
    <li>발송 환경 : {environment}</li>
    <li>첨부 리포트 : {report_name}</li>
    <li>상태 : SUCCESS</li>
  </ul>
</body>
</html>
"""


def build_message(sender, recipient, subject, html_body, report_path):
    message = MIMEMultipart("mixed")
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject

    body_part = MIMEMultipart("alternative")
    body_part.attach(MIMEText(html_body, "html", "utf-8"))
    message.attach(body_part)

    report_file = Path(report_path)
    attachment = MIMEApplication(report_file.read_bytes(), _subtype="html")
    attachment.add_header("Content-Disposition", "attachment", filename=report_file.name)
    message.attach(attachment)
    return message


def send_test_mail():
    sender = os.getenv(SENDER_ENV)
    password = os.getenv(PASSWORD_ENV)
    if not sender or not password:
        missing = [name for name, value in ((SENDER_ENV, sender), (PASSWORD_ENV, password)) if not value]
        raise RuntimeError(f"환경변수가 설정되지 않았습니다: {', '.join(missing)}")

    report_path = get_latest_report()
    if not report_path:
        raise RuntimeError("첨부할 HTML 리포트가 없습니다. 먼저 reports/price_report_YYYYMMDD_HHMMSS.html 파일을 생성해주세요.")

    sent_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    environment = current_environment()
    html_body = build_html_body(sent_at, environment, report_path)
    message = build_message(sender, RECIPIENT, SUBJECT, html_body, report_path)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
        server.login(sender, password)
        server.sendmail(sender, [RECIPIENT], message.as_string())

    print(f"Test mail sent to {RECIPIENT} from {sender} at {sent_at} ({environment})")
    print(f"Attached report: {report_path}")


if __name__ == "__main__":
    send_test_mail()
