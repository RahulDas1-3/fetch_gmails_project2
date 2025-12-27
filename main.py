# main.py

from __future__ import annotations

from auth import GmailAuth
from reader import GmailReader
from sender import GmailSender
from ai_reply import ReplySuggester
from utils import extract_plain_text_from_payload, get_header


def _choose_reply_text(suggester: ReplySuggester, email_text: str) -> str | None:
    """Return the reply text to send, or None to cancel."""

    try:
        s1, s2 = suggester.suggest_two(email_text=email_text)
    except Exception as e:
        print(f"⚠️  Could not generate AI suggestions: {e}")
        s1, s2 = "", ""

    if s1 or s2:
        print("\n🤖 AI Reply Suggestions")
        print("=" * 60)
        if s1:
            print("(1)\n" + s1)
            print("-" * 60)
        if s2:
            print("(2)\n" + s2)
            print("=" * 60)

    print("\nChoose reply option:")
    print("1) Send suggestion 1")
    print("2) Send suggestion 2")
    print("3) Write/edit reply manually")
    print("4) Cancel")

    pick = input("Your choice (1-4): ").strip()
    if pick == "1" and s1:
        base = s1
    elif pick == "2" and s2:
        base = s2
    elif pick == "3":
        base = ""
    else:
        print("Cancelled.")
        return None

    # If they picked an AI suggestion, allow editing before sending
    if base:
        print("\nSelected text (you can edit it now). Leave blank to keep as-is.")
        print("-" * 60)
        print(base)
        print("-" * 60)
        edited = input("Edit reply (or press Enter to keep): ").rstrip()
        return edited if edited else base

    # Manual compose
    manual = input("Type your reply: ").rstrip()
    if not manual:
        print("Empty reply. Cancelled.")
        return None
    return manual


def _reply_flow(sender: GmailSender, suggester: ReplySuggester, messages: list[dict]) -> None:
    if not messages:
        return

    want = input("\nReply to one of these emails now? (y/N): ").strip().lower().startswith("y")
    if not want:
        return

    try:
        idx = int(input("Which index do you want to reply to? (e.g., 1): ").strip())
    except ValueError:
        print("Invalid index.")
        return

    if idx < 1 or idx > len(messages):
        print("Invalid index.")
        return

    msg = messages[idx - 1]
    payload = msg.get("payload", {}) or {}
    headers = payload.get("headers", []) or []
    subject = get_header(headers, "Subject") or "(no subject)"
    frm = get_header(headers, "From") or "(unknown sender)"

    body_text = extract_plain_text_from_payload(payload) or ""
    email_text = (body_text or msg.get("snippet", "") or "").strip()

    if not email_text:
        print("⚠️  Could not extract any text from this email to build suggestions.")
        email_text = f"From: {frm}\nSubject: {subject}"

    print("\nReplying to:")
    print(f"From: {frm}")
    print(f"Subject: {subject}")

    reply_text = _choose_reply_text(suggester=suggester, email_text=email_text)
    if not reply_text:
        return

    original_id = msg.get("id")
    if not original_id:
        print("❌ Missing message ID; cannot reply.")
        return

    sender.reply(original_message_id=original_id, reply_text=reply_text)


def main() -> None:
    auth = GmailAuth()
    reader = GmailReader(auth)
    sender = GmailSender(auth)
    suggester = ReplySuggester()

    while True:
        print("\nGmail Utility (Modules & Classes)")
        print("1) Fetch last N mails (then reply)")
        print("2) Fetch last N mails by email address (then reply)")
        print("3) Send an email (with attachments)")
        print("4) Exit")
        choice = input("\nChoose an option (1-4): ").strip()

        if choice == "1":
            try:
                n = int(input("How many messages? ").strip())
            except ValueError:
                n = 5
            mark = input("Mark as read? (y/N): ").strip().lower().startswith("y")

            messages = reader.fetch_last_n(n=n, mark_as_read=mark)
            _reply_flow(sender=sender, suggester=suggester, messages=messages)

        elif choice == "2":
            email_addr = input("Email address to filter (e.g., alice@example.com): ").strip()
            try:
                n = int(input("How many messages? ").strip())
            except ValueError:
                n = 5
            mark = input("Mark as read? (y/N): ").strip().lower().startswith("y")

            messages = reader.fetch_last_n_by_email(email_address=email_addr, n=n, mark_as_read=mark)
            _reply_flow(sender=sender, suggester=suggester, messages=messages)

        elif choice == "3":
            to_addr = input("To: ").strip()
            subject = input("Subject: ").strip()
            body = input("Body: ").strip()
            attach_input = input("Attachments (comma-separated paths, blank for none): ").strip()
            attachments = [p.strip() for p in attach_input.split(",")] if attach_input else []
            sender.send(to=to_addr, subject=subject, body=body, attachments=attachments)

        elif choice == "4":
            print("Goodbye!")
            break

        else:
            print("Invalid choice. Try again.")


if __name__ == "__main__":
    main()