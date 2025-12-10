import re
from typing import Any, List, Dict, Optional, Tuple, TextIO, Union
from .constants import (
    COMMA, TAB, PIPE, COLON, SPACE, NEWLINE,
    ESCAPE_MAP, UNESCAPE_MAP
)
from .errors import TOONDecodeError

class LineReader:
    def __init__(self, doc: str, indent_size: int = 2):
        self.doc = doc
        self.lines = []
        self.doc_lines = doc.splitlines(keepends=True)
        
        for i, raw_line in enumerate(self.doc_lines):
            stripped = raw_line.rstrip('\r\n')
            if not stripped or stripped.isspace():
                continue 
            
            indent_len = 0
            for char in stripped:
                if char == ' ': indent_len += 1
                elif char == '\t': indent_len += 1 
                else: break
            
            content = stripped[indent_len:]
            indent_level = indent_len // indent_size
            self.lines.append({
                'indent': indent_level,
                'content': content,
                'idx': i,
                'raw': raw_line
            })
            
        self.pos = 0

    def peek(self) -> Optional[Dict]:
        if self.pos < len(self.lines):
            return self.lines[self.pos]
        return None

    def advance(self) -> Optional[Dict]:
        line = self.peek()
        if line: self.pos += 1
        return line

    def get_error_pos(self, line_data):
        total = 0
        for i in range(line_data['idx']):
            total += len(self.doc_lines[i])
        return total + (line_data['indent'] * 2) 

class TOONDecoder:
    def __init__(self, strict: bool = False):
        self.strict = strict

    def decode(self, s: str) -> Any:
        reader = LineReader(s)
        first = reader.peek()
        if not first: return {}

        # Root form discovery
        # Array header?
        header_info, inline_content = self._try_parse_array_header_line(first['content'])
        if first['indent'] == 0 and header_info:
             reader.advance()
             return self._parse_array_body(reader, 0, header_info, inline_content)
        
        # Primitive? (1 line, not k:v)
        if len(reader.lines) == 1 and not self._is_key_value(first['content']):
             reader.advance()
             return self._parse_primitive(first['content'], COMMA)
        
        # Object
        return self._parse_object(reader, indent_level=0)

    def _parse_object(self, reader: LineReader, indent_level: int) -> Dict[str, Any]:
        obj = {}
        while True:
            line = reader.peek()
            if not line: break
            if line['indent'] < indent_level: break
            
            if line['indent'] > indent_level:
                raise TOONDecodeError(f"Unexpected indentation", self.doc([line]), reader.get_error_pos(line))

            reader.advance()
            
            key_part, val_part, has_colon = self._split_key_value(line['content'])
            if not has_colon:
                raise TOONDecodeError(f"Expected key:value, got {line['content']}", "", reader.get_error_pos(line))
                
            # Check if key part is actually an array header? "key[N]:"
            # We append colon to key_part because _try_parse checks for ending with colon (or needs context)
            # Actually _try_parse expects full header string including colon.
            # key_part from _split_key_value excludes the colon.
            # So reconstruction: header_string = key_part + ":"
            header_info, _ = self._try_parse_array_header_line(key_part + ":")
            
            if header_info:
                 actual_key = header_info['key']
                 obj[actual_key] = self._parse_array_body(reader, indent_level, header_info, val_part)
            else:
                 decoded_key = self._parse_key(key_part)
                 if val_part:
                     obj[decoded_key] = self._parse_primitive(val_part, COMMA) 
                 else:
                     # Nested value
                     next_line = reader.peek()
                     if next_line and next_line['indent'] > indent_level:
                         if next_line['content'].startswith('- '):
                             # Spec 10: Objects as list items.
                             # If we have "key:\n - ..."
                             # This is likely an expanded list.
                             # But TOON requires array headers [N].
                             # If permissive, maybe allow? But let's stick to object default logic (nested object).
                             obj[decoded_key] = self._parse_object(reader, indent_level + 1)
                         else:
                             obj[decoded_key] = self._parse_object(reader, indent_level + 1)
                     else:
                         obj[decoded_key] = {}
        return obj

    def _parse_array_body(self, reader, indent_level, header, inline_content):
        # Header has N, delimiter.
        N = header['length']
        delim = header['delim']
        
        if inline_content and inline_content.strip():
             vals = self.parse_delimited_values(inline_content, delim)
             return [self._parse_primitive(v, delim) for v in vals]
        
        if header['fields']:
             return self._parse_tabular_rows(reader, indent_level + 1, header)
        
        return self._parse_list_items(reader, indent_level + 1, header)

    def _parse_tabular_rows(self, reader, indent_level, header):
        rows = []
        fields = header['fields']
        delim = header['delim']
        N = header['length']
        
        while True:
            line = reader.peek()
            if not line: break
            if line['indent'] < indent_level: break
            reader.advance()
            
            vals = self.parse_delimited_values(line['content'], delim)
            if len(vals) != len(fields):
                 if self.strict: raise TOONDecodeError(f"Row length mismatch", "", 0)
            
            row_obj = {}
            for i, f in enumerate(fields):
                val_str = vals[i] if i < len(vals) else ""
                row_obj[f] = self._parse_primitive(val_str, delim)
            rows.append(row_obj)
            
        return rows

    def _parse_list_items(self, reader, indent_level, header):
        items = []
        N = header['length']
        
        while True:
            line = reader.peek()
            if not line: break
            if line['indent'] < indent_level: break
            
            content = line['content']
            if not content.startswith('- '):
                break 
                
            reader.advance()
            item_text = content[2:]
            
            # Check for array header
            header_info, inline = self._try_parse_array_header_line(item_text)
            if header_info and header_info['key'] is None: 
                 items.append(self._parse_array_body(reader, indent_level + 1, header_info, inline))
                 continue
            
            kp, vp, has_c = self._split_key_value(item_text)
            if has_c:
                 first_key = self._parse_key(kp)
                 item_obj = {first_key: self._parse_primitive(vp, COMMA)}
                 rest_obj = self._parse_object(reader, indent_level + 1)
                 item_obj.update(rest_obj)
                 items.append(item_obj)
            else:
                 items.append(self._parse_primitive(item_text, COMMA))

        return items

    def _parse_array_header(self, text: str) -> Optional[Dict]:
        info, _ = self._try_parse_array_header_line(text)
        return info

    def _try_parse_array_header_line(self, text: str) -> Tuple[Optional[Dict], str]:
        idx = self._find_char_unquoted(text, ':')
        if idx == -1: return None, ""
        
        potential_header = text[:idx+1]
        inline_content = text[idx+1:].strip()
        
        b_start = potential_header.find('[')
        if b_start == -1: return None, ""
        b_end = potential_header.find(']', b_start)
        if b_end == -1: return None, ""
        
        key_part = potential_header[:b_start]
        bracket_content = potential_header[b_start+1:b_end]
        remainder = potential_header[b_end+1:-1]
        
        if not bracket_content: return None, ""
        delim = COMMA
        if bracket_content[-1] in (TAB, PIPE):
             delim = bracket_content[-1]
             length_str = bracket_content[:-1]
        else:
             length_str = bracket_content
             
        if not length_str.isdigit(): return None, ""
        length = int(length_str)
        
        fields = []
        if remainder.startswith('{') and remainder.endswith('}'):
             f_content = remainder[1:-1]
             fields = self.parse_delimited_values(f_content, delim) 
        
        info = {
            'key': key_part if key_part else None,
            'length': length,
            'delim': delim,
            'fields': fields
        }
        return info, inline_content

    def _split_key_value(self, text: str) -> Tuple[str, str, bool]:
        idx = self._find_char_unquoted(text, ':')
        if idx == -1: return text, "", False
        return text[:idx].strip(), text[idx+1:].strip(), True

    def _find_char_unquoted(self, text: str, char: str) -> int:
        in_quote = False
        bs = False
        for i, c in enumerate(text):
            if c == '\\': 
                bs = not bs
                continue
            if c == '"' and not bs:
                in_quote = not in_quote
            bs = False
            if c == char and not in_quote:
                return i
        return -1

    def parse_delimited_values(self, text: str, delimiter: str) -> List[str]:
        vals = []
        current = []
        in_quote = False
        bs = False
        
        for c in text:
            if c == '\\':
                bs = not bs
                current.append(c)
                continue
            if c == '"' and not bs:
                in_quote = not in_quote
                current.append(c)
                bs = False
                continue
            
            bs = False
            
            if c == delimiter and not in_quote:
                vals.append("".join(current).strip())
                current = []
            else:
                current.append(c)
                
        vals.append("".join(current).strip())
        return vals

    def _parse_key(self, text: str) -> str:
        if text.startswith('"') and text.endswith('"'):
            return self._unescape_string(text[1:-1])
        return text

    def _parse_primitive(self, text: str, delimiter: str) -> Any:
        if text.startswith('"'): 
             if not text.endswith('"'): raise TOONDecodeError("Unterminated string", "", 0)
             return self._unescape_string(text[1:-1])
        if text == 'true': return True
        if text == 'false': return False
        if text == 'null': return None
        if re.match(r'^-?\d+(\.\d+)?([eE][+-]?\d+)?$', text):
             if text.startswith('0') and len(text)>1 and text[1]!='.': return text
             try:
                 return float(text) if ('.' in text or 'e' in text.lower()) else int(text)
             except: pass
        return text

    def _unescape_string(self, text: str) -> str:
        parts = []
        i = 0
        l = len(text)
        while i < l:
             if text[i] == '\\' and i+1 < l:
                 c = text[i+1]
                 if c == 'n': parts.append('\n')
                 elif c == 'r': parts.append('\r')
                 elif c == 't': parts.append('\t')
                 elif c == '"': parts.append('"')
                 elif c == '\\': parts.append('\\')
                 else: parts.append('\\' + c) 
                 i += 2
             else:
                 parts.append(text[i])
                 i += 1
        return "".join(parts)

    def _is_key_value(self, text: str) -> bool:
        return self._find_char_unquoted(text, ':') != -1

    def doc(self, line):
        return ""

def loads(s: str) -> Any:
    return TOONDecoder().decode(s)

def load(fp: TextIO) -> Any:
    return loads(fp.read())
