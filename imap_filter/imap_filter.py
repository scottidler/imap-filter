from imapclient import IMAPClient
from imap_filter.message import Message
from imap_filter.message_filter import MessageFilter
from ruamel.yaml import YAML

class IMAPFilter:
    def __init__(self, imap_domain: str, imap_username: str, imap_password: str, filters=None, **yargs):
        self.imap_domain = imap_domain
        self.imap_username = imap_username
        self.imap_password = imap_password
        self.filters = [MessageFilter(f) for f in (filters or [])]
        print('filters:')
        for f in self.filters:
            print(f)
        self.client = self.get_imap_client()

    def get_imap_client(self):
        client = IMAPClient(self.imap_domain)
        client.login(self.imap_username, self.imap_password)
        client.select_folder("INBOX")
        return client

    def fetch_messages(self):
        self.client.select_folder("INBOX")
        message_uids = self.client.search(["ALL"])
        if not message_uids:
            return []

        print(f'len(messages)={len(message_uids)}')

        messages = self.client.fetch(message_uids, ["RFC822"])
        return [
            Message.from_email_message(uid, data[b"RFC822"])
            for uid, data in messages.items()
            if b"RFC822" in data
        ]

    def move_imbox_to_inbox(self):
        """Moves all messages from Imbox back to Inbox for retesting."""
        self.client.select_folder("Imbox")
        message_uids = self.client.search(["ALL"])
        if not message_uids:
            print("No messages in Imbox to move.")
            return

        print(f"Moving {len(message_uids)} messages from Imbox to Inbox...")
        self.client.move(message_uids, "INBOX")
        print("Move completed.")

    def apply_filters(self, messages):
        """Applies filters in sequence, ensuring first match wins."""
        for message_filter in self.filters:
            matched_messages = [msg for msg in messages if message_filter.compare(msg)]

            if matched_messages:
                if message_filter.move:
                    self.move(matched_messages, message_filter.move)

                if message_filter.star:
                    self.star(matched_messages)

                if message_filter.mark:
                    self.mark(matched_messages)

            messages = [msg for msg in messages if msg not in matched_messages]

    def star(self, msgs):
        if msgs:
            result = self.client.add_gmail_labels([msg.uid for msg in msgs], ["\\Starred"], silent=False)
            print('*'*80)
            print("RESULT:", result)
            print('*'*80)

    def mark(self, msgs):
        if msgs:
            result = self.client.add_gmail_labels([msg.uid for msg in msgs], ["\\Important"], silent=False)
            print('*'*80)
            print("RESULT:", result)
            print('*'*80)

    def move(self, msgs, location):
        if msgs:
            self.client.move([msg.uid for msg in msgs], location)

    def execute(self):
        self.move_imbox_to_inbox()
        messages = self.fetch_messages()
        self.apply_filters(messages)
