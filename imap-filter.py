#!/usr/bin/env python3

import os
import re
import sys
sys.dont_write_bytecode = True

REAL_FILE = os.path.abspath(__file__)
REAL_NAME = os.path.basename(REAL_FILE)
REAL_PATH = os.path.dirname(REAL_FILE)
if os.path.islink(__file__):
    LINK_FILE = REAL_FILE; REAL_FILE = os.path.abspath(os.readlink(__file__))
    LINK_NAME = REAL_NAME; REAL_NAME = os.path.basename(REAL_FILE)
    LINK_PATH = REAL_PATH; REAL_PATH = os.path.dirname(REAL_FILE)

DIR = os.path.abspath(os.path.dirname(__file__))
CWD = os.path.abspath(os.getcwd())
REL = os.path.relpath(DIR, CWD)

NAME, EXT = os.path.splitext(REAL_NAME)

IMAP_DOMAIN = os.environ.get('IMAP_DOMAIN', 'imap.gmail.com')
IMAP_USERNAME = os.environ.get('IMAP_USERNAME', 'scott.idler@tatari.tv')
IMAP_PASSWORD = os.environ.get('IMAP_PASSWORD', None)

import logging

logging.basicConfig(
    format='%(asctime)s - %(levelname)s: %(message)s',
    level=logging.INFO
)
import email
import json
from fnmatch import fnmatch
from ruamel import yaml
from datetime import datetime
from collections import OrderedDict
from backports.zoneinfo import ZoneInfo
from leatherman.yaml import yaml_print
from leatherman.fuzzy import fuzzy
from imapclient import IMAPClient, RECENT
from argparse import ArgumentParser, RawDescriptionHelpFormatter

def clean(s):
    if s != None:
        s = s.replace('\r\n\t', '').replace('"', '')
    return s

def compare(test, items):
    if isinstance(test, list):
        return test == items
    return any([fnmatch(item, test) for item in items])

class MessageFilter:
    def __init__(self, to, cc, fr, move, star):
        self.to = to
        self.cc = cc
        self.fr = fr
        self.move = move
        self.star = star

    def filter(self, message):
        if self.cc and compare(self.cc, message.cc):
            return False
        #if compare(self.cc, message.cc) and

class Message:
    def __init__(self, count, uid, data):
        self.count = count
        self.uid = uid
        self._zoneinfo = ZoneInfo('US/Pacific')
        self._regex = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}')
        self._data = email.message_from_bytes(data[b'RFC822'])
        self._to = self._data.get('To')
        self._cc = self._data.get('Cc')
        self._fr = self._data.get('From')
        self._sub = self._data.get('Subject')
        self._date = self._data.get('Date')

    def _emails(self, s):
        if s != None:
            return self._regex.findall(s)
        return []

    @property
    def to(self):
        return self._emails(self._to)

    @property
    def cc(self):
        return self._emails(self._cc)

    @property
    def fr(self):
        return self._emails(self._fr)[0]

    @property
    def sub(self):
        return re.sub('\n|\r|\t', '', self._sub.strip())

    @property
    def date(self):
        result = email.utils.parsedate_to_datetime(self._date)
        return result.astimezone(self._zoneinfo)

    def __repr__(self):
        fields = ', '.join([
            f'{k}={v}'
            for k,v
            in self.json().items()
        ])
        return f'Message({fields})'

    def json(self):
        return OrderedDict({
            k:v
            for k,v
            in {
                'to': self.to,
                'cc': self.cc,
                'from': self.fr,
                'subject': self.sub,
                'date': self.date,
                'uid': self.uid,
                'count': self.count,
            }.items()
            if v
        })

def main(args):
    parser = ArgumentParser(
        description=__doc__,
        formatter_class=RawDescriptionHelpFormatter,
        add_help=False)
    parser.add_argument(
        '-c', '--config',
        metavar='FILEPATH',
        default='%(REL)s/%(NAME)s.yml' % globals(),
        help='default="%(default)s"; config filepath')
    ns, rem = parser.parse_known_args(args)
    try:
        config = {
            key.replace('-', '_'): value
            for key, value
            in yaml.safe_load(open(ns.config)).items()
        }
    except FileNotFoundError as er:
        config = dict()
    parser = ArgumentParser(
        parents=[parser])
    parser.set_defaults(**config)
    parser.add_argument(
        '--domain',
        default=IMAP_DOMAIN,
        help='default="%(default)s"; imap domain')
    parser.add_argument(
        '--username',
        default=IMAP_USERNAME,
        help='default="%(default)s"; imap username')
    parser.add_argument(
        '--password',
        default=IMAP_PASSWORD,
        help='default="%(default)s"; imap password')
    ns = parser.parse_args()
    print(ns)

    with IMAPClient(ns.domain) as server:
        server.login(ns.username, ns.password)
        server.select_folder('INBOX', readonly=True)
        messages = server.gmail_search('in:unread and after:2021/11/29')
        messages = server.gmail_search('to:scott.idler@tatari.tv and after:2021/11/29')
        for count, (uid, data) in enumerate(server.fetch(messages, 'RFC822').items()):
            msg = Message(count, uid, data)
            #yaml_print(dict(message=msg.json()))
            yaml_print(msg.json())
            print()

if __name__ == '__main__':
    main(sys.argv[1:])

