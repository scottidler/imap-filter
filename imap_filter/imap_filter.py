from imapclient import IMAPClient
from imap_filter.message import Message
from imap_filter.message_filter import MessageFilter
from ruamel.yaml import YAML
from loguru import logger

def print_filtered_summary(message_filter, matched_messages):
    """
    Prints a summary of filtered messages with actions taken.

    Args:
        message_filter (MessageFilter): The filter that was applied.
        matched_messages (list of Message): List of messages that matched the filter.
    """
    action_icons = {
        "star": "⭐",
        "mark": "✅",
        "move": "➡️"
    }

    print("\nFiltered Messages Summary:")
    for msg in matched_messages:
        actions = []
        if message_filter.star:
            actions.append(action_icons["star"])
        if message_filter.mark:
            actions.append(action_icons["mark"])
        if message_filter.move:
            actions.append(f"{action_icons['move']} {message_filter.move}")
        subject = msg.sub[:76]
        print(f"- {subject} {' '.join(actions)}")

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

    def fetch_messages(self, folder="INBOX", query=["ALL"]):
        """
        Fetches messages from the specified folder matching the given query.
        `query` should be a list of IMAP search criteria.
        """
        logger.info(f"Fetching messages from folder {folder} with query {query}")
        self.client.select_folder(folder)
        message_uids = self.client.search(query)
        if not message_uids:
            logger.info(f"No messages found in {folder} matching {query}.")
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

    def apply_filters(self):
        """
        Processes each filter as an ACL. For each filter, if the folder and query
        are the same as the previous filter, use the remaining unfiltered messages;
        otherwise, execute a new fetch.
        """
        current_folder = None
        current_query = None
        messages = []

        for message_filter in self.filters:
            if (message_filter.folder != current_folder or message_filter.query != current_query) or messages is None:
                current_folder = message_filter.folder
                current_query = message_filter.query
                messages = self.fetch_messages(current_folder, current_query)
            count = len(messages)
            print(f"\nAgainst {count} messages {message_filter}")
            matched = [(msg, msg.uid) for msg in messages if message_filter.compare(msg)]
            if matched:
                matched_messages, uids = zip(*matched)
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

                matched_count = len(uids)
                print(f"{matched_count}/{count} messages filtered after completing {message_filter.name}. {count - matched_count} unmatched.")
                print_filtered_summary(message_filter, matched_messages)
                messages = [msg for msg in messages if msg not in [m for m, _ in matched]]
            else:
                logger.info(f"No messages matched filter '{message_filter.name}'.")

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
        return self.apply_filters()
