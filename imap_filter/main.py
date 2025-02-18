import os
import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from ruamel.yaml import YAML
from imap_filter.imap_filter import IMAPFilter
from leatherman.dictionary import head_body
from loguru import logger

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
LOG_FILE = os.path.join(BASE_DIR, "../imap-filter.log")

IMAP_DOMAIN = os.getenv("IMAP_DOMAIN")
IMAP_USERNAME = os.getenv("IMAP_USERNAME")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")

yaml = YAML()

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logger.remove()
logger.add(LOG_FILE, level=LOG_LEVEL, rotation="10MB", retention="7 days")

def ensure_list(value):
    """Ensure that a YAML value is always a list."""
    if isinstance(value, list):
        return value if isinstance(value, list) else [value]
    return []

def load_config(config_path):
    """Loads the YAML config file and ensures required fields exist."""
    config_path = os.path.abspath(config_path)

    if not os.path.isfile(config_path):
        logger.error(f"Config file not found: {config_path}")
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r") as f:
        config = yaml.load(f) or {}

    if not config.get("filters"):
        logger.error(f"Config file {config_path} is missing required 'filters' section.")
        raise ValueError(f"Config file {config_path} is missing required 'filters' section.")

    return config

def parse_args():
    parser = ArgumentParser(
        description="IMAP email filtering CLI",
        formatter_class=RawDescriptionHelpFormatter,
        add_help=False
    )
    parser.add_argument(
        '-c', '--config',
        metavar='FILEPATH',
        default=os.path.join(BASE_DIR, "../imap-filter.yml"),
        help='Path to the configuration file (default: %(default)s)'
    )
    ns, _ = parser.parse_known_args()
    config = load_config(ns.config)

    parser = ArgumentParser(parents=[parser])
    parser.set_defaults(**config)
    parser.add_argument("--imap-domain", type=str, default=IMAP_DOMAIN, help="IMAP domain")
    parser.add_argument("--imap-username", type=str, default=IMAP_USERNAME, help="IMAP username")
    parser.add_argument("--imap-password", type=str, default=IMAP_PASSWORD, help="IMAP password")

    return parser.parse_args()

def main():
    try:
        ns = parse_args()
        filters = ns.filters

        if not filters:
            logger.error("No filters found in configuration. Exiting.")
            raise ValueError("No filters found in configuration. Exiting.")

        logger.info(f"Starting IMAP filter on {ns.imap_domain} as {ns.imap_username}")

        imap_filter = IMAPFilter(
            ns.imap_domain,
            ns.imap_username,
            ns.imap_password,
            filters
        )

        imap_filter.execute()
        logger.info("Filtering completed.")

    except Exception as e:
        logger.exception(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
