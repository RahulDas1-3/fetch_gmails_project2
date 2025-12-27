# sender.py

import os
import base64
import mimetypes
from email.message import EmailMessage
from typing import List, Optional, Union

from googleapiclient.errors import HttpError

from auth import GmailAuth
from utils import get_header


class GmailSender:
    """Sends emails (with attachments) and replies to existing threads."""

    def __init__(self, auth: GmailAuth):
        self.service = auth.get_service()

    def send(
        self,
        to: Union[str, List[str]],
        subject: str,
        body: str,
        attachments: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Send an email. `to` can be:
          - "a@x.com"
          - ["a@x.com", "b@y.com"]  (joined with comma)
        """
        try:
            if isinstance(to, list):
                to = ", ".join([x.strip() for x in to if x.strip()])

            msg = EmailMessage()
            msg["To"] = to
            msg["From"] = "me"
            msg["Subject"] = subject
            msg.set_content(body)

            # Attach files
            if attachments:
                for path in attachments:
                    path = path.strip()
                    if not path:
                        continue
                    if not os.path.isfile(path):
                        print(f"⚠️ Skipping, not found: {path}")
                        continue

                    content_type, encoding = mimetypes.guess_type(path)
                    if content_type is None or encoding is not None:
                        content_type = "application/octet-stream"
                    main_type, sub_type = content_type.split("/", 1)

                    with open(path, "rb") as f:
                        file_data = f.read()

                    msg.add_attachment(
                        file_data,
                        maintype=main_type,
                        subtype=sub_type,
                        filename=os.path.basename(path),
                    )

            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            sent = self.service.users().messages().send(userId="me", body={"raw": raw}).execute()
            print(f"✅ Sent! Message ID: {sent.get('id')}")
            return sent.get("id")

        except HttpError as e:
            print(f"❌ Send error: {e}")
            return None

    def reply(self, original_message_id: str, reply_text: str) -> Optional[str]:
        """
        Replies to a specific message ID with proper threading.
        """
        try:
            original = self.service.users().messages().get(
                userId="me", id=original_message_id, format="full"
            ).execute()

            thread_id = original.get("threadId")
            headers = original.get("payload", {}).get("headers", [])

            from_addr = get_header(headers, "From")
            subject = get_header(headers, "Subject")
            message_id_hdr = get_header(headers, "Message-ID")

            if subject and not subject.lower().startswith("re:"):
                subject = "Re: " + subject

            msg = EmailMessage()
            msg["From"] = "me"
            msg["To"] = from_addr
            if subject:
                msg["Subject"] = subject
            if message_id_hdr:
                msg["In-Reply-To"] = message_id_hdr
                msg["References"] = message_id_hdr

            msg.set_content(reply_text)

            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            body = {"raw": raw, "threadId": thread_id} if thread_id else {"raw": raw}

            sent = self.service.users().messages().send(userId="me", body=body).execute()
            print(f"✅ Reply sent! Message ID: {sent.get('id')}")
            return sent.get("id")

        except HttpError as e:
            print(f"❌ Reply error: {e}")
            return None