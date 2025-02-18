import fnmatch
from leatherman.repr import __repr__

class AddressFilterError(Exception):
    def __init__(self, spec):
        msg = f'Error AddressFilter requires a list or scalar string; patterns={spec} of type {type(spec)}'
        super().__init__(msg)

class AddressFilter:
    def __init__(self, spec):
        if isinstance(spec, str):
            self.patterns = [spec]
        elif isinstance(spec, list):
            self.patterns = spec
        else:
            raise AddressFilterError(spec)

    def compare(self, addresses):
        if self.patterns == [] and addresses == []:
            return True
        return any(fnmatch.fnmatch(addr.lower(), pattern.lower()) for addr in addresses for pattern in self.patterns)

    __repr__ = __repr__
