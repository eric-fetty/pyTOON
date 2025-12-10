class TOONError(Exception):
    """Base exception for all TOON errors."""
    pass

class TOONDecodeError(TOONError):
    """Raised when decoding TOON fails."""
    def __init__(self, msg, doc, pos):
        lineno = doc.count('\n', 0, pos) + 1
        colno = pos - doc.rfind('\n', 0, pos)
        errmsg = '%s: line %d column %d (char %d)' % (msg, lineno, colno, pos)
        super().__init__(errmsg)
        self.msg = msg
        self.doc = doc
        self.pos = pos
        self.lineno = lineno
        self.colno = colno

class TOONEncodeError(TOONError):
    """Raised when encoding TOON fails."""
    pass
