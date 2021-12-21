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

IMAP_DOMAIN = os.environ.get('IMAP_DOMAIN')
IMAP_USERNAME = os.environ.get('IMAP_USERNAME')
IMAP_PASSWORD = os.environ.get('IMAP_PASSWORD')

import logging

logging.basicConfig(
    format='%(asctime)s - %(levelname)s: %(message)s',
    level=logging.INFO
)
import email
import json
from addict import Addict
from fnmatch import fnmatch
from ruamel import yaml
from datetime import datetime
from collections import OrderedDict
from backports.zoneinfo import ZoneInfo
from leatherman.dbg import dbg
from leatherman.yaml import yaml_print
from leatherman.dictionary import head_body
from leatherman.repr import __repr__
from imapclient import IMAPClient, RECENT
from argparse import ArgumentParser, RawDescriptionHelpFormatter

from leatherman import fuzzy

def clean(s):
    if s != None:
        s = s.replace('\r\n\t', '').replace('"', '')
    return s

def compare(test, items):
    if isinstance(test, list):
        return test == items
    return any([fnmatch(item, test) for item in items])

class ScalarToMultipleError(Exception):
    def __init__(self, obj):
        msg = f'scalar to multiple error on obj={obj}'
        super().__init__(msg)

def listify(obj):
    if isinstance(obj, str) or isinstance(obj, int):
        return [obj]
    if obj == {} or obj == None:
        return []
    if isinstance(obj, tuple):
        return list(obj)
    if isinstance(obj, list):
        return obj
    raise ScalarToMultipleError(obj)

def ensure_defaults(obj, matches=1):
    return Addict(
        patterns=obj.patterns if obj.patterns != {} else [],
        matches=obj.matches if obj.matches != {} else matches
    )

def update(d, **kwargs):
    d.update(**kwargs)
    return d

class MessageFilter:
    def __init__(self, spec):
        name, body = head_body(spec)
        self.name = name
        self.to = body.to if body.to != {} else None
        self.cc = body.cc if body.cc != {} else None
        self.fr = body.dr if body.fr != {} else None
        self.move = body.move
        self.star = body.star

    __repr__ = __repr__

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
            #if v
        })

class IMAPFilter:
    def __init__(self, imap_domain=None, imap_username=None, imap_password=None, filters=None, folders=None, **kwargs):
        self.filters = filters
        self.folders = folders
        self.client = IMAPClient(imap_domain)
        self.client.login(imap_username, imap_password)
        self.client.select_folder('INBOX')

    __repr__ = __repr__

    @property
    def messages(self):
        gmail_search = 'to:scott.idler@tatari.tv and after:2021/12/12'
        ids = self.client.gmail_search(gmail_search)
        return [
            Message(count, uid, data)
            for count, (uid, data)
            in enumerate(self.client.fetch(ids, 'RFC822').items())
        ]

    @property
    def message_filters(self):
        return [
            MessageFilter(f)
            for f
            in self.filters
        ]

    def compare_message(self, message, message_filter):
        if message_filter.to

    def apply_filter(self, messages, message_filter):
        for message in messages:

        return messages

    def execute(self):
        messages = self.messages
        for mf in self.message_filters:
            messages = self.apply_filter(mf, messages)
        self.client.shutdown()
        print('execution complete')

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
        config = Addict({
            key.replace('-', '_'): value
            for key, value
            in yaml.safe_load(open(ns.config)).items()
        })
    except FileNotFoundError as er:
        config = dict()
    parser = ArgumentParser(
        parents=[parser])
    parser.set_defaults(**config)
    parser.add_argument(
        '--imap-domain',
        default=os.environ.get('IMAP_DOMAIN', config.get('imap_domain')),
        help='default="%(default)s"; imap domain')
    parser.add_argument(
        '--imap-username',
        default=os.environ.get('IMAP_USERNAME', config.get('imap_username')),
        help='default="%(default)s"; imap username')
    parser.add_argument(
        '--imap-password',
        default=os.environ.get('IMAP_PASSWORD', config.get('imap_password')),
        help='default="%(default)s"; imap password')
    ns = parser.parse_args()

    ifilter = IMAPFilter(**ns.__dict__)
    ifilter.execute()
#    assert ns.imap_password != None, 'imap-password is required'
#    with IMAPClient(ns.imap_domain) as server:
#        server.login(ns.imap_username, ns.imap_password)
#        server.select_folder('INBOX', readonly=True)
#        ids = server.gmail_search('to:scott.idler@tatari.tv and after:2021/12/12')
#        messages = [
#            Message(count, uid, data)
#            for count, (uid, data)
#            in enumerate(server.fetch(ids, 'RFC822').items())
#        ]
#        print('total:', len(messages))
#        yaml_print([m.to for m in messages])
#        print()
#        for mf in [MessageFilter(f) for f in ns.filters]:
#            if mf.to:
#                messages1 = [
#                    message
#                    for message
#                    in messages
#                    if message.to == mf.to
#                ]
#            if mf.cc:
#                messages1 = [
#                    message
#                    for message
#                    in messages
#                    if message.cc == mf.cc
#                ]
#            for m in messages1:
#                yaml_print(m.json())

if __name__ == '__main__':
    main(sys.argv[1:])

