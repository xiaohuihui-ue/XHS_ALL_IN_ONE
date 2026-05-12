from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from backend.app.core.config import get_settings


def send_password_reset_email(to_email: str, reset_url: str) -> None:
    settings = get_settings()
    if not settings.smtp_host:
        raise RuntimeError("SMTP not configured")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "重置你的密码"
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to_email

    text = f"请访问以下链接重置密码（30 分钟内有效）：\n\n{reset_url}\n\n如果你没有申请重置密码，请忽略此邮件。"
    html = f"""\
<html><body>
<p>请点击以下链接重置密码（<strong>30 分钟内有效</strong>）：</p>
<p><a href="{reset_url}">{reset_url}</a></p>
<p>如果你没有申请重置密码，请忽略此邮件。</p>
</body></html>"""

    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    if settings.smtp_tls:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.sendmail(msg["From"], [to_email], msg.as_string())
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.sendmail(msg["From"], [to_email], msg.as_string())
