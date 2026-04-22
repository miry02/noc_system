"""
NOC Email Sender
Sends the generated report + attachments to the configured recipients.
Uses smtplib (built-in) — no extra packages needed.

Outlook/Office 365 settings:
  SMTP Host: smtp.office365.com
  SMTP Port: 587
  Auth: your full work email + your normal password
  (No App Password needed for Outlook — use your regular work credentials)
"""
import smtplib
import json
import os
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "email_config.json")

DEFAULT_CONFIG = {
    "smtp_host": "smtp.office365.com",
    "smtp_port": 587,
    "sender_email": "",
    "sender_password": "",   # your normal Outlook/work password
    "recipients": [],
    "cc": []
}


def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def send_report(report_path: str, agent_name: str, shift_type: str,
                extra_attachments: list = None) -> tuple[bool, str]:
    """
    Send the report email.
    Returns (success: bool, message: str)
    """
    config = load_config()

    if not config.get("sender_email") or not config.get("recipients"):
        return False, "Email not configured. Please set up email in Settings."

    try:
        msg = MIMEMultipart()
        msg["From"] = config["sender_email"]
        msg["To"] = ", ".join(config["recipients"])
        if config.get("cc"):
            msg["Cc"] = ", ".join(config["cc"])

        date_str = datetime.now().strftime("%d/%m/%Y")
        msg["Subject"] = f"NOC Shift Report – {shift_type} – {date_str} – {agent_name}"

        body = f"""Dear Team,

Please find attached the NOC Shift Report for the {shift_type} shift on {date_str}.

Agent: {agent_name}
Shift: {shift_type}
Report Generated: {datetime.now().strftime("%d/%m/%Y %H:%M")}

This report was generated automatically by the NOC Report System.

Regards,
NOC Operations
"""
        msg.attach(MIMEText(body, "plain"))

        # Attach main report
        attachments = [report_path] + (extra_attachments or [])
        for path in attachments:
            if path and os.path.exists(path):
                with open(path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename={os.path.basename(path)}"
                )
                msg.attach(part)

        # Connect and send
        with smtplib.SMTP(config["smtp_host"], config["smtp_port"]) as server:
            server.ehlo()
            server.starttls()
            server.login(config["sender_email"], config["sender_password"])
            all_recipients = config["recipients"] + config.get("cc", [])
            server.sendmail(config["sender_email"], all_recipients, msg.as_string())

        return True, f"Report sent successfully to {len(config['recipients'])} recipient(s)."

    except smtplib.SMTPAuthenticationError:
        return False, "Authentication failed. Check your email and App Password in Settings."
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        return False, f"Failed to send email: {str(e)}"
