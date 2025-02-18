from imapclient import IMAPClient
from imap_filter.message import Message
from imap_filter.message_filter import MessageFilter
from ruamel.yaml import YAML
from loguru import logger

class IMAPFilter:
    def __init__(self, imap_domain: str, imap_username: str, imap_password: str, filters=None, **yargs):
        self.imap_domain = imap_domain
        self.imap_username = imap_username
        self.imap_password = imap_password
        self.filters = [MessageFilter(f) for f in (filters or [])]

        logger.info(f"Filters loaded: {self.filters}")

        self.client = self.get_imap_client()
        logger.debug(f"IMAP Capabilities: {self.client.capabilities()}")

    def get_imap_client(self):
        client = IMAPClient(self.imap_domain)
        client.login(self.imap_username, self.imap_password)
        client.select_folder("INBOX", readonly=False)
        return client

    def fetch_messages(self):
        self.client.select_folder("INBOX")
        message_uids = self.client.search(["ALL"])

        if not message_uids:
            logger.info("No messages found.")
            return []

        logger.info(f"Fetching {len(message_uids)} messages...")
        messages = self.client.fetch(message_uids, ["RFC822"])

        return [
            Message.from_email_message(uid, data[b"RFC822"])
            for uid, data in messages.items()
            if b"RFC822" in data
        ]

    def move_imbox_to_inbox(self):
        """Moves all messages from Imbox back to Inbox for retesting."""
        self.client.select_folder("Imbox", readonly=False)
        message_uids = self.client.search(["ALL"])
        if not message_uids:
            logger.info("No messages in Imbox to move.")
            return

        logger.info(f"Moving {len(message_uids)} messages from Imbox to Inbox...")
        self.client.move(message_uids, "INBOX")
        logger.info("Move completed.")

    def apply_filters(self, messages):

        for message_filter in self.filters:
            count = len(messages)
            print(f"\nAgainst {count} messages {message_filter}")

            matched_messages, uids = zip(
                *[(msg, msg.uid) for msg in messages if message_filter.compare(msg)]
            )

            if uids:
                logger.info(f"Filter '{message_filter.name}' matched UIDs: {uids}")

                if message_filter.move:
                    logger.info(f"Moving messages {uids} to {message_filter.move}")
                    self.move(uids, message_filter.move)

                if message_filter.star:
                    logger.info(f"Starring messages {uids}")
                    self.star(uids)

                if message_filter.mark:
                    logger.info(f"Marking messages {uids}")
                    self.mark(uids)

                matched = len(uids)
                print(f"{matched}/{count} messages filtered after completing {message_filter.name}. {count-matched} remaining.")
            messages = [msg for msg in messages if msg not in matched_messages]

    def star(self, uids):
        if uids:
            logger.info(f"Starring messages: {uids}")
            response = self.client.add_gmail_labels(uids, ["\\Starred"])
            logger.debug(f"Response from add_gmail_labels: {response}")
            fetched_labels = self.client.get_gmail_labels(uids)
            logger.debug(f"Labels after operation: {fetched_labels}")

    def mark(self, uids):
        if uids:
            logger.info(f"Marking messages as Important: {uids}")
            response = self.client.add_gmail_labels(uids, ['\\Important'], silent=False)
            logger.debug(f"Response from add_gmail_labels: {response}")

    def move(self, uids, location):
        if uids:
            logger.info(f"Moving messages {uids} to {location}")
            self.client.move(uids, location)

    def execute(self):
        self.move_imbox_to_inbox()
        messages = self.fetch_messages()
        return self.apply_filters(messages)
