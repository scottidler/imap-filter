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

from leatherman.fuzzy import fuzzy

def clean(s):
    if s != None:
        s = s.replace('\r\n\t', '').replace('"', '')
    return s

def compare(test, items):
    if isinstance(test, list):
        return test == items
    return any([fnmatch(item, test) for item in items])

class ListifyError(Exception):
    def __init__(self, obj):
        msg = f'listify error on obj={obj}'
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
    raise ListifyError(obj)

def ensure_defaults(obj, matches=1):
    return Addict(
        patterns=obj.patterns if obj.patterns != {} else [],
        matches=obj.matches if obj.matches != {} else matches
    )

def update(d, **kwargs):
    d.update(**kwargs)
    return d

class AddressFilterError(Exception):
    def __init__(self, obj):
        msg = f'address filter error obj={obj}'
        super().__init__(msg)

class AddressFilter:
    def __init__(self, spec):
        #self.spec = spec
        if spec == None:
            self.matches = None
            self.patterns = None
        elif isinstance(spec, dict):
            self.matches = spec.get('matches', None)
            self.patterns = spec.get('patterns', None)
        elif isinstance(spec, list):
            if any(map(lambda item: '*' in item, spec)):
                self.matches = None
                self.patterns = spec
            else:
                self.matches = spec
                self.patterns = None
        elif isinstance(spec, str):
            if '*' in spec:
                self.matches = None
                self.patterns = [spec]
            else:
                self.matches = [spec]
                self.patterns = None
        else:
            raise AddressFilterError(spec)

    @property
    def passthru(self):
        return self.matches == None and self.patterns == None

    __repr__ = __repr__

    def compare(self, addresses):
        if self.matches == None and self.patterns == None:
            return True
        if self.matches != None:
            if sorted(self.matches) == sorted(addresses):
                return True
            if all(map(lambda m: m in addresses, self.matches)):
                addresses = sub(addresses, self.matches)
            else:
                return False
        if self.patterns != None:
            matches = [
                address
                for address
                in addresses
                if any(map(lambda p: fnmatch(address, p), self.patterns))
            ]
            if matches:
                addresses = sub(addresses, matches)
                return True
            return False
        elif addresses:
            return False
        return True

class MessageFilter:
    def __init__(self, spec):
        name, body = head_body(spec)
        self.name = name
        self.to = AddressFilter(body.to)
        self.cc = AddressFilter(body.cc)
        self.fr = AddressFilter(body.fr)
        self.move = body.move
        self.star = body.star

    __repr__ = __repr__

    def compare(self, message):
        if not self.to.compare(message.to):
            return False
        if not self.cc.compare(message.cc):
            return False
        if not self.fr.compare(message.fr):
            return False
        return True

#    def apply(self, message, client):
#        if self.compare(message):
#            client.copy
#            return True
#        return False

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
        return self._emails(self._fr)

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
        })

def sub(list1, list2):
    return list(set(list1) - set(list2))

class IMAPFilter:
    def __init__(self, imap_domain=None, imap_username=None, imap_password=None, filters=None, folders=None, **kwargs):
        self.filters = [
            MessageFilter(f)
            for f
            in filters
        ]
        self.folders = folders
        self.client = IMAPClient(imap_domain)
        assert imap_password != None, 'imap-password is required'
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

    def apply_filter(self, message_filter, messages):
        filtered = [
            message
            for message
            in messages
            if message_filter.compare(message)
        ]
        if filtered:
            uids = [
                m.uid
                for m
                in filtered
            ]
            if message_filter.move:
                logging.info(f'move uids={uids} to {message_filter.move}')
                self.client.move(uids, message_filter.move)
            if message_filter.star:
                logging.info(f'star uids={uids} with "\\Starred"')
                self.client.set_gmail_labels(uids, '\\Starred')

        return filtered

    def execute(self):
        messages = self.messages
        for mf in self.filters:
            filtered = self.apply_filter(mf, messages)
            print(mf)
            [
                print(' ', message)
                for message
                in filtered
            ]
            print('*'*80)
            messages = list(set(messages) - set(filtered))
        self.client.shutdown()
        print('execution complete')

def load(config):
    try:
        return Addict({
            key.replace('-', '_'): value
            for key, value
            in yaml.safe_load(open(config)).items()
        })
    except FileNotFoundError as er:
        return dict()

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
    config = load(ns.config)
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

if __name__ == '__main__':
    main(sys.argv[1:])

