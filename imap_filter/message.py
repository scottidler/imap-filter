import email
from datetime import datetime
from email.utils import getaddresses, parsedate_to_datetime
from zoneinfo import ZoneInfo
from leatherman.repr import __repr__

class Message:
    def __init__(self, uid: int, fr: list, to: list, cc: list, sub: str, date: datetime):
        self.uid = uid
        self.fr = fr
        self.to = to
        self.cc = cc
        self.sub = sub
        self.date = date.astimezone(ZoneInfo("America/Los_Angeles"))

    @classmethod
    def from_email_message(cls, uid, data):
        parsed_email = email.message_from_bytes(data)

        def extract_emails(address_list):
            return [email for name, email in getaddresses(address_list) if email]

        fr = extract_emails(parsed_email.get_all("From", []))
        to = extract_emails(parsed_email.get_all("To", []))
        cc = extract_emails(parsed_email.get_all("Cc", []))

        sub = parsed_email.get("Subject", "").strip()
        date_header = parsed_email.get("Date")
        date = parsedate_to_datetime(date_header) if date_header else None

        if date is None:
            raise ValueError(f"Missing or unparsable Date header in message UID {uid}")

        return cls(uid, fr, to, cc, sub, date)

    __repr__ = __repr__
