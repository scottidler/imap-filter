import pprint
from imap_filter.address_filter import AddressFilter
from leatherman.repr import __repr__
from leatherman.dictionary import head_body

pp = pprint.PrettyPrinter(indent=4, depth=2)

class MessageFilter:
    def __init__(self, spec):
        name, body = head_body(spec)
        self.name = name
        self.fr = AddressFilter(body["from"]) if "from" in body else None
        self.to = AddressFilter(body["to"]) if "to" in body else None
        self.cc = AddressFilter(body["cc"]) if "cc" in body else None
        self.move = body.get("move")
        self.star = body.get("star", False)
        self.mark = body.get("mark", False)

    def compare(self, message):
        if self.fr:
            if not self.fr.compare(message.fr):
                return False
        if self.to:
            if not self.to.compare(message.to):
                return False
        if self.cc:
            if not self.cc.compare(message.cc):
                return False
        return True

    __repr__ = __repr__
