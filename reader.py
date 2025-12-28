# reader.py

from __future__ import annotations

import os
from typing import Dict, List, Optional

from googleapiclient.errors import HttpError

from auth import GmailAuth
from utils import get_header, extract_plain_text_from_payload


# ---------------- LangChain mail categorizer ----------------
class MailCategorizer:
    """
    Categorize emails into one of: work, personal, spam, urgent

    Uses LangChain + OpenAI if available and OPENAI_API_KEY is set.
    Falls back to a simple keyword heuristic if LangChain/OpenAI isn't available.
    """

    ALLOWED = {"work", "personal", "spam", "urgent"}

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.0):
        self.model = model
        self.temperature = temperature
        self._chain = None

        # Lazy import so the rest of the tool still works even if langchain isn't installed
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import StrOutputParser

            prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "You are an email classifier. "
                        "Return EXACTLY one label from: work, personal, spam, urgent. "
                        "No extra words, punctuation, or explanation.",
                    ),
                    (
                        "human",
                        "Classify this email.\n\n"
                        "From: {from_addr}\n"
                        "To: {to_addr}\n"
                        "Subject: {subject}\n"
                        "Body:\n{body}\n",
                    ),
                ]
            )

            llm = ChatOpenAI(model=self.model, temperature=self.temperature)
            self._chain = prompt | llm | StrOutputParser()

        except Exception:
            self._chain = None

    def classify(self, from_addr: str, to_addr: str, subject: str, body: str) -> str:
        # If LangChain is ready and API key exists, use it
        if self._chain is not None and os.getenv("OPENAI_API_KEY"):
            try:
                # Keep token usage sane: truncate body if huge
                body_in = body if len(body) <= 5000 else body[:5000] + "\n...(truncated)..."
                out = self._chain.invoke(
                    {
                        "from_addr": from_addr or "",
                        "to_addr": to_addr or "",
                        "subject": subject or "",
                        "body": body_in or "",
                    }
                )
                label = (out or "").strip().lower()
                if label in self.ALLOWED:
                    return label
            except Exception:
                pass  # fall through to heuristic

        # Heuristic fallback (no extra deps)
        return self._heuristic(from_addr, subject, body)

    def _heuristic(self, from_addr: str, subject: str, body: str) -> str:
        text = f"{from_addr}\n{subject}\n{body}".lower()

        urgent_kw = ["urgent", "asap", "immediately", "deadline", "overdue", "action required"]
        spam_kw = ["unsubscribe", "winner", "prize", "lottery", "free", "buy now", "limited offer", "click here"]
        work_kw = ["meeting", "invoice", "project", "deadline", "contract", "interview", "hr", "client", "report"]

        if any(k in text for k in urgent_kw):
            return "urgent"
        if any(k in text for k in spam_kw):
            return "spam"
        if any(k in text for k in work_kw):
            return "work"
        return "personal"


class GmailReader:
    """
    Reads emails:
      - fetch_last_n: last n recent inbox mails (with optional mark-as-read)
      - fetch_last_n_by_email: last n mails filtered by an email address
    Enforced constraints:
      - Display ONLY: From, To, Subject, Body
      - Keep indexing
      - Categorize each mail: work/personal/spam/urgent (LangChain if available)
    """

    def __init__(self, auth: GmailAuth):
        self.service = auth.get_service()
        self.categorizer = MailCategorizer()

    def _fetch_full_messages(self, ids: List[str]) -> List[Dict]:
        full_msgs: List[Dict] = []
        for mid in ids:
            try:
                m = self.service.users().messages().get(userId="me", id=mid, format="full").execute()
                m["id"] = mid  # keep at top level
                full_msgs.append(m)
            except HttpError as e:
                print(f"⚠️ Could not fetch {mid}: {e}")
        return full_msgs

    def _print_minimal_message(self, index: int, msg: Dict):
        payload = msg.get("payload", {})
        headers = payload.get("headers", [])

        from_addr = get_header(headers, "From")
        to_addr = get_header(headers, "To")
        subject = get_header(headers, "Subject")
        body_text = extract_plain_text_from_payload(payload) or ""

        category = self.categorizer.classify(
            from_addr=from_addr or "",
            to_addr=to_addr or "",
            subject=subject or "",
            body=body_text or "",
        )

        # ---- Only these fields (plus index + category) ----
        print(f"\n[{index}]")
        print(f"From: {from_addr}")
        print(f"To: {to_addr}")
        print(f"Subject: {subject}")
        print(f"Category: {category}")
        print("Body:")
        print(body_text.strip() if body_text.strip() else "(no plain-text body found)")
        print("-" * 60)

    # -------- Feature 1: Fetch last n inbox mails --------
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
                self._print_minimal_message(i, msg)

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

    # -------- Feature 2: Fetch last n mails filtered by an email address --------
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
                self._print_minimal_message(i, msg)

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