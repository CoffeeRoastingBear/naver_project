import os
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SENDER_ENV = "GMAIL_ID"
PASSWORD_ENV = "GMAIL_APP_PASSWORD"
RECIPIENT = "seongjin.son@samsung.com"
SUBJECT = "[TEST] 가격 트래킹 메일 자동화 테스트"


def current_environment():
    return "GitHub Actions" if os.getenv("GITHUB_ACTIONS") == "true" else "Local"


def build_html_body(sent_at, environment):
    return f"""<!DOCTYPE html>
<html lang="ko">
<body>
  <h2>메일 자동화 테스트</h2>
  <p>GitHub Actions 기반 메일 발송 테스트입니다.</p>
  <ul>
    <li>발송 시간 : {sent_at}</li>
    <li>발송 환경 : {environment}</li>
    <li>상태 : SUCCESS</li>
  </ul>
</body>
</html>
"""


def build_message(sender, recipient, subject, html_body):
    message = MIMEMultipart("alternative")
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.attach(MIMEText(html_body, "html", "utf-8"))
    return message


def send_test_mail():
    sender = os.getenv(SENDER_ENV)
    password = os.getenv(PASSWORD_ENV)
    if not sender or not password:
        missing = [name for name, value in ((SENDER_ENV, sender), (PASSWORD_ENV, password)) if not value]
        raise RuntimeError(f"환경변수가 설정되지 않았습니다: {', '.join(missing)}")

    sent_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    environment = current_environment()
    html_body = build_html_body(sent_at, environment)
    message = build_message(sender, RECIPIENT, SUBJECT, html_body)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
        server.login(sender, password)
        server.sendmail(sender, [RECIPIENT], message.as_string())

    print(f"Test mail sent to {RECIPIENT} from {sender} at {sent_at} ({environment})")


if __name__ == "__main__":
    send_test_mail()
