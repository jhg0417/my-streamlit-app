"""Gmail SMTP: do not call without explicit UI approval."""
from email.message import EmailMessage
from email.utils import parseaddr
import smtplib


def send_email(to: str, subject: str, body: str, address: str, app_password: str):
    _, email = parseaddr(to)
    if not email or "@" not in email or not subject.strip() or not body.strip():
        raise ValueError("수신자 이메일, 제목, 본문을 확인해 주세요.")
    if not address or not app_password:
        raise ValueError("Secrets에 Gmail 주소와 앱 비밀번호가 없습니다.")
    msg = EmailMessage()
    msg["From"] = address
    msg["To"] = email
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
        server.login(address, app_password)
        server.send_message(msg)
    return email
