import os
import smtplib
import ssl
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from report_generator import get_latest_report, get_latest_report_meta


SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SENDER_ENV = "GMAIL_ID"
PASSWORD_ENV = "GMAIL_APP_PASSWORD"
RECIPIENT = "seongjin.son@samsung.com"
SUBJECT = "[TEST] TV 가격 트래킹 리포트"


def current_environment():
    return "GitHub Actions" if os.getenv("GITHUB_ACTIONS") == "true" else "Local"


def _summary_html(summary_lines):
    lines = summary_lines or ["AI 요약 정보가 없습니다."]
    return "".join(f"<li>{line}</li>" for line in lines[:3])


def build_html_body(sent_at, environment, report_path, summary_lines=None):
    report_name = Path(report_path).name if report_path else "-"
    return f"""<!DOCTYPE html>
<html lang="ko">
<body>
  <div style="font-family:Arial,'Malgun Gothic',sans-serif;color:#17202a;max-width:720px;">
    <div style="border:1px solid #d9e0e8;border-radius:10px;overflow:hidden;">
      <div style="background:#142235;color:#ffffff;padding:18px 20px;">
        <h2 style="margin:0;font-size:22px;">&lt;&lt; AI 요약 &gt;&gt;</h2>
        <p style="margin:8px 0 0;color:#c8d3e0;font-size:13px;">오전 10시 기준 운영 발송 구조 테스트</p>
      </div>
      <div style="padding:18px 20px;background:#ffffff;">
        <ol style="margin:0 0 16px 20px;padding:0;line-height:1.7;">
          {_summary_html(summary_lines)}
        </ol>
        <table style="border-collapse:collapse;width:100%;font-size:13px;">
          <tr>
            <td style="border-top:1px solid #edf1f5;padding:8px;color:#667085;width:120px;">발송 시간</td>
            <td style="border-top:1px solid #edf1f5;padding:8px;">{sent_at}</td>
          </tr>
          <tr>
            <td style="border-top:1px solid #edf1f5;padding:8px;color:#667085;">발송 환경</td>
            <td style="border-top:1px solid #edf1f5;padding:8px;">{environment}</td>
          </tr>
          <tr>
            <td style="border-top:1px solid #edf1f5;padding:8px;color:#667085;">첨부 리포트</td>
            <td style="border-top:1px solid #edf1f5;padding:8px;">{report_name}</td>
          </tr>
        </table>
        <p style="margin:16px 0 0;color:#667085;font-size:12px;">정적 HTML 리포트와 캡처 이미지를 함께 첨부했습니다.</p>
      </div>
    </div>
  </div>
</body>
</html>
"""


def _attach_file(message, path):
    file_path = Path(path)
    if not file_path.exists():
        return
    if file_path.suffix.lower() == ".png":
        attachment = MIMEImage(file_path.read_bytes(), _subtype="png")
    else:
        attachment = MIMEApplication(file_path.read_bytes(), _subtype=file_path.suffix.lstrip(".") or "octet-stream")
    attachment.add_header("Content-Disposition", "attachment", filename=file_path.name)
    message.attach(attachment)


def build_message(sender, recipient, subject, html_body, report_path):
    message = MIMEMultipart("mixed")
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject

    body_part = MIMEMultipart("alternative")
    body_part.attach(MIMEText(html_body, "html", "utf-8"))
    message.attach(body_part)

    _attach_file(message, report_path)
    _attach_file(message, Path(report_path).with_suffix(".png"))
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
    meta = get_latest_report_meta()
    html_body = build_html_body(sent_at, environment, report_path, meta.get("summary"))
    message = build_message(sender, RECIPIENT, SUBJECT, html_body, report_path)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
        server.login(sender, password)
        server.sendmail(sender, [RECIPIENT], message.as_string())

    print(f"Test mail sent to {RECIPIENT} from {sender} at {sent_at} ({environment})")
    print(f"Attached report: {report_path}")


if __name__ == "__main__":
    send_test_mail()
