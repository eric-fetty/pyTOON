import re

# Delimiters
COMMA = ','
TAB = '\t'
PIPE = '|'
COLON = ':'
SPACE = ' '
NEWLINE = '\n'

# Escapes (Section 7.1)
ESCAPE_MAP = {
    '\\': '\\\\',
    '"': '\\"',
    '\n': '\\n',
    '\r': '\\r',
    '\t': '\\t',
}
UNESCAPE_MAP = {v: k for k, v in ESCAPE_MAP.items()}

# Regex patterns
# Key: unquoted-key = ( ALPHA / "_" ) *( ALPHA / DIGIT / "_" / "." )
RE_UNQUOTED_KEY = re.compile(r'^[A-Za-z_][A-Za-z0-9_.]*$')

# Numeric checks (Section 7.2)
# Matches /^-?\d+(?:\.\d+)?(?:e[+-]?\d+)?$/i
RE_NUMERIC = re.compile(r'^-?\d+(?:\.\d+)?(?:e[+-]?\d+)?$', re.IGNORECASE)
# Matches /^0\d+$/ (leading-zero decimals)
RE_LEADING_ZERO = re.compile(r'^-?0\d+$')
