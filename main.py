# main.py

from auth import GmailAuth
from reader import GmailReader
from sender import GmailSender
from ai_reply import ReplySuggester
from utils import extract_plain_text_from_payload


def main():
    auth = GmailAuth()
    reader = GmailReader(auth)
    sender = GmailSender(auth)

    # LangChain suggester
    suggester = ReplySuggester()

    while True:
        print("\nGmail Utility (Modules & Classes)")
        print("1) Fetch last N mails")
        print("2) Fetch last N mails by email address")
        print("3) Reply to one of the last N mails (by index) + 2 AI suggestions")
        print("4) Send an email (with attachments)")
        print("5) Exit")

        choice = input("\nChoose an option (1-5): ").strip()

        if choice == "1":
            try:
                n = int(input("How many messages? ").strip())
            except ValueError:
                n = 5
            mark = input("Mark as read? (y/N): ").strip().lower().startswith("y")
            reader.fetch_last_n(n=n, mark_as_read=mark)

        elif choice == "2":
            email_addr = input("Email address to filter (e.g., alice@example.com): ").strip()
            try:
                n = int(input("How many messages? ").strip())
            except ValueError:
                n = 5
            mark = input("Mark as read? (y/N): ").strip().lower().startswith("y")
            reader.fetch_last_n_by_email(email_address=email_addr, n=n, mark_as_read=mark)

        elif choice == "3":
            try:
                n = int(input("Look at how many recent messages? ").strip())
                idx = int(input("Which index to reply to? (1-based) ").strip())
            except ValueError:
                print("Invalid number.")
                continue

            # Fetch and validate
            messages = reader.fetch_last_n(n=n, mark_as_read=False)
            if not messages:
                print("No messages to reply to.")
                continue

            if idx < 1 or idx > len(messages):
                print("Invalid index.")
                continue

            msg = messages[idx - 1]
            msg_id = msg.get("id")
            payload = msg.get("payload", {})
            email_body = extract_plain_text_from_payload(payload) or msg.get("snippet", "")

            if not msg_id:
                print("Missing message ID.")
                continue

            print("\n🤖 Generating 2 reply suggestions using LangChain...\n")
            try:
                s1, s2 = suggester.suggest_two(email_body)
            except Exception as e:
                print("❌ AI suggestion failed. You can still type your reply manually.")
                print(f"Error: {e}")
                s1, s2 = "", ""

            if s1:
                print("------ Suggestion 1 (Professional/Direct) ------")
                print(s1)
                print("------------------------------------------------\n")

            if s2:
                print("------ Suggestion 2 (Warm/Professional) --------")
                print(s2)
                print("------------------------------------------------\n")

            print("Choose reply option:")
            print("1) Use Suggestion 1")
            print("2) Use Suggestion 2")
            print("M) Write reply manually")

            pick = input("Your choice (1/2/M): ").strip().lower()

            if pick == "1" and s1:
                reply_text = s1
            elif pick == "2" and s2:
                reply_text = s2
            else:
                reply_text = input("\nType your reply:\n> ").strip()

            if not reply_text:
                print("❌ Empty reply. Cancelled.")
                continue

            sender.reply(original_message_id=msg_id, reply_text=reply_text)

        elif choice == "4":
            to_addr = input("To (single or comma-separated): ").strip()
            if not to_addr:
                print("❌ Missing recipient.")
                continue

            to_list = [x.strip() for x in to_addr.split(",") if x.strip()]
            subject = input("Subject: ").strip()
            body = input("Body: ").strip()

            attach_input = input("Attachments (comma-separated paths, blank for none): ").strip()
            attachments = [p.strip() for p in attach_input.split(",")] if attach_input else []

            sender.send(to=to_list if len(to_list) > 1 else to_list[0], subject=subject, body=body, attachments=attachments)

        elif choice == "5":
            print("Goodbye!")
            break

        else:
            print("Invalid choice. Try again.")


if __name__ == "__main__":
    main()