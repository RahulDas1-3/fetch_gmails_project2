# reader.py

from typing import Dict, List
from googleapiclient.errors import HttpError

from auth import GmailAuth
from utils import get_header, extract_plain_text_from_payload


class GmailReader:
    """
    Reads emails:
      - fetch_last_n: last n recent inbox mails (with optional mark-as-read)
      - fetch_last_n_by_email: last n mails filtered by an email address
    """

    def __init__(self, auth: GmailAuth):
        self.service = auth.get_service()

    def _print_message_summary(self, msg: Dict, index: int | None = None):
        payload = msg.get("payload", {})
        headers = payload.get("headers", [])
        frm = get_header(headers, "From")
        subject = get_header(headers, "Subject")
        date = get_header(headers, "Date")
        snippet = msg.get("snippet", "")
        body_text = extract_plain_text_from_payload(payload)

        prefix = f"[{index}] " if index is not None else ""
        print(f"{prefix}🆔 ID: {msg.get('id')}")
        print(f"📨 From: {frm}")
        print(f"🧾 Subject: {subject}")
        print(f"🗓  Date: {date}")
        print(f"🔎 Snippet: {snippet}")

        if body_text:
            preview = body_text if len(body_text) <= 800 else body_text[:800] + "\n…(truncated)…"
            print("— Body (plain text):")
            print(preview)
        else:
            print("— Body: (no plain-text part found)")

        print("-" * 60)

    def _fetch_full_messages(self, ids: List[str]) -> List[Dict]:
        full_msgs: List[Dict] = []
        for mid in ids:
            try:
                m = self.service.users().messages().get(userId="me", id=mid, format="full").execute()
                m["id"] = mid
                full_msgs.append(m)
            except HttpError as e:
                print(f"⚠️ Could not fetch {mid}: {e}")
        return full_msgs

    def fetch_last_n(self, n: int = 5, mark_as_read: bool = False) -> List[Dict]:
        try:
            listed = self.service.users().messages().list(userId="me", q="in:inbox", maxResults=n).execute()
            msgs_meta = listed.get("messages", []) or []
            if not msgs_meta:
                print("📭 No messages found.")
                return []

            ids = [m["id"] for m in msgs_meta]
            full_msgs = self._fetch_full_messages(ids)

            for i, msg in enumerate(full_msgs, start=1):
                self._print_message_summary(msg, index=i)

                if mark_as_read and "UNREAD" in msg.get("labelIds", []):
                    try:
                        self.service.users().messages().modify(
                            userId="me",
                            id=msg["id"],
                            body={"removeLabelIds": ["UNREAD"], "addLabelIds": []},
                        ).execute()
                    except HttpError as e:
                        print(f"⚠️ Could not mark as read for {msg['id']}: {e}")

            return full_msgs

        except HttpError as e:
            print(f"❌ Read error: {e}")
            return []

    def fetch_last_n_by_email(self, email_address: str, n: int = 5, mark_as_read: bool = False) -> List[Dict]:
        if not email_address:
            print("Please provide an email address.")
            return []

        query = f'(from:{email_address}) OR (to:{email_address})'
        try:
            listed = self.service.users().messages().list(userId="me", q=query, maxResults=n).execute()
            msgs_meta = listed.get("messages", []) or []
            if not msgs_meta:
                print("📭 No messages found for that address.")
                return []

            ids = [m["id"] for m in msgs_meta]
            full_msgs = self._fetch_full_messages(ids)

            for i, msg in enumerate(full_msgs, start=1):
                self._print_message_summary(msg, index=i)

                if mark_as_read and "UNREAD" in msg.get("labelIds", []):
                    try:
                        self.service.users().messages().modify(
                            userId="me",
                            id=msg["id"],
                            body={"removeLabelIds": ["UNREAD"], "addLabelIds": []},
                        ).execute()
                    except HttpError as e:
                        print(f"⚠️ Could not mark as read for {msg['id']}: {e}")

            return full_msgs

        except HttpError as e:
            print(f"❌ Read error: {e}")
            return []