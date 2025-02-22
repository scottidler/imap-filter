import pprint
from imap_filter.address_filter import AddressFilter
from leatherman.repr import __repr__
from leatherman.dictionary import head_body

pp = pprint.PrettyPrinter(indent=4, depth=2)

class ListifyError(Exception):
    def __init__(self, obj):
        msg = f'Error: listify given {obj} of type {type(obj)}'
        super().__init__(msg)

def listify(obj):
    if isinstance(obj, list):
        return obj
    if isinstance(obj, str):
        return [obj]
    raise ListifyError(obj)

class MessageFilter:
    def __init__(self, spec):
        name, body = head_body(spec)
        self.name = name
        self.folder = body.get("folder", "INBOX")
        self.query = listify(body.get("query", "ALL"))
        self.fr = AddressFilter(listify(body["from"])) if "from" in body else None
        self.to = AddressFilter(body["to"]) if "to" in body else None
        self.cc = AddressFilter(body["cc"]) if "cc" in body else None
        self.star = body.get("star", False)
        self.mark = body.get("mark", False)
        self.move = body.get("move")

    def compare(self, message):
        if self.fr and not self.fr.compare(message.fr):
            return False
        if self.to and not self.to.compare(message.to):
            return False
        if self.cc and not self.cc.compare(message.cc):
            return False
        return True

    def __str__(self):
        return (
            f"\nApplying filter: {self.name}\n"
            f"  folder: {self.folder}\n"
            f"  query: {self.query}\n"
            f"  from: {self.fr.patterns if self.fr else '[]'}\n"
            f"  to: {self.to.patterns if self.to else '[]'}\n"
            f"  cc: {self.cc.patterns if self.cc else '[]'}\n"
            f"  star: {self.star}\n"
            f"  mark: {self.mark}\n"
            f"  move: {self.move}\n"
        )

    __repr__ = __repr__
