import re
from io import StringIO
from typing import Any, List, Dict, Optional, TextIO, Tuple, Set
from .constants import (
    COMMA, TAB, PIPE, COLON, SPACE, NEWLINE,
    RE_UNQUOTED_KEY, RE_NUMERIC, RE_LEADING_ZERO,
    ESCAPE_MAP
)
from .errors import TOONEncodeError

class TOONEncoder:
    def __init__(self, indent_size: int = 2, delimiter: str = COMMA):
        self.indent_size = indent_size
        self.delimiter = delimiter
        self._indent_str = ' ' * indent_size

    def encode(self, obj: Any) -> str:
        buffer = StringIO()
        
        # Root handling
        if isinstance(obj, dict):
            if not obj:
                return "" # Empty object at root
            self._encode_object_fields(obj, buffer, 0, is_root=True)
        elif isinstance(obj, (list, tuple)):
            self._encode_root_array(obj, buffer)
        else:
            # Root primitive
            buffer.write(self._format_primitive(obj, self.delimiter))
            
        return buffer.getvalue()

    def _encode_value(self, key: Optional[str], value: Any, buffer: TextIO, depth: int, is_list_item: bool = False):
        indent = self._indent_str * depth
        prefix = ""
        
        if is_list_item:
            # List items handled by caller usually, but if we are here...
            # Actually caller should handle the "- " prefix processing.
            pass
        
        encoded_key = ""
        if key is not None:
            encoded_key = self._format_key(key)

        if isinstance(value, dict):
            # Object
            if not value:
                # Empty object
                if key is not None:
                     buffer.write(f"{indent}{encoded_key}:{NEWLINE}")
                else:
                     # Should not happen for standard structures if caller handles correctly
                     pass
            else:
                if key is not None:
                    buffer.write(f"{indent}{encoded_key}:{NEWLINE}")
                    self._encode_object_fields(value, buffer, depth + 1)
                else:
                    # Anonymous object (shouldn't happen in standard key:val, mainly in lists)
                    pass

        elif isinstance(value, (list, tuple)):
            # Array
            self._encode_array(key, value, buffer, depth)

        else:
            # Primitive
            encoded_val = self._format_primitive(value, self.delimiter) # Use document delimiter for object fields
            if key is not None:
                buffer.write(f"{indent}{encoded_key}: {encoded_val}{NEWLINE}")
            else:
                # Value only (rare case here)
                pass

    def _encode_object_fields(self, obj: Dict[str, Any], buffer: TextIO, depth: int, is_root: bool = False):
        first = True
        indent = self._indent_str * depth
        
        for key, value in obj.items():
            if not first:
                # No separation needed between fields other than newlines from previous writes
                pass
            
            # Check type of value to decide format
            if isinstance(value, (dict, list, tuple)):
                # Complex
                # Spec: "key: alone for nested... nested fields at depth+1"
                pass 
                
            self._encode_value(key, value, buffer, depth)
            first = False

    def _encode_array(self, key: Optional[str], arr: List[Any], buffer: TextIO, depth: int):
        indent = self._indent_str * depth
        encoded_key = self._format_key(key) if key else ""
        N = len(arr)
        
        # 1. Try Primitive Inline
        if self._is_primitive_array(arr):
            # key[N]: v1,v2...
            # We need to choose a delimiter that minimizes quoting? Default to comma.
            values = [self._format_primitive(v, self.delimiter) for v in arr]
            line = self.delimiter.join(values)
            # If root array: [N]: ...
            header = f"{encoded_key}[{N}]:" if key else f"[{N}]:"
            if N > 0:
                 buffer.write(f"{indent}{header} {line}{NEWLINE}")
            else:
                 buffer.write(f"{indent}{header}{NEWLINE}")
            return

        # 2. Try Tabular (Uniform Objects)
        keys = self._get_uniform_keys(arr)
        if keys:
            # key[N]{f1,f2}:
            # Row...
            field_names = list(keys)
            encoded_fields = [self._format_key(k) for k in field_names]
            fields_str = self.delimiter.join(encoded_fields)
            
            header = f"{encoded_key}[{N}]{{{fields_str}}}:" if key else f"[{N}]{{{fields_str}}}:"
            buffer.write(f"{indent}{header}{NEWLINE}")
            
            row_indent = self._indent_str * (depth + 1)
            for item in arr:
                row_values = []
                for k in field_names:
                    row_values.append(self._format_primitive(item[k], self.delimiter))
                buffer.write(f"{row_indent}{self.delimiter.join(row_values)}{NEWLINE}")
            return

        # 3. Expanded List (Mixed/Complex)
        header = f"{encoded_key}[{N}]:" if key else f"[{N}]:"
        buffer.write(f"{indent}{header}{NEWLINE}")
        
        item_indent = self._indent_str * (depth + 1)
        for item in arr:
            self._encode_list_item(item, buffer, depth + 1)

    def _encode_list_item(self, item: Any, buffer: TextIO, depth: int):
        indent = self._indent_str * depth
        
        if isinstance(item, (dict)):
            # Object in list
            # Format: - key: (first key), then indented
            # Or - key[N]...
            if not item:
                # Empty object in list?
                # - {} ? No, spec says object starts with first key.
                # If empty object, maybe just "- " but that's invalid if no fields?
                # Spec 10: "If the object is empty, there are no lines." -> Wait.
                # Let's assume non-empty for now or skip.
                # Actually, spec doesn't explicitly handle empty objects in lists well besides maybe just "-"? 
                # But "- " expects something.
                # Let's write "- " and nothing? No.
                # For now let's handle non-empty.
                pass
            
            # Find first key
            first_key, first_val = list(item.items())[0]
            encoded_first_key = self._format_key(first_key)
            
            # We need to print "- first_key: val"
            # It's like encoding a value but prefixed with "- "
            
            # Construct the first line prefix
            prefix = f"{indent}- "
            
            # If first val is complex?
            if isinstance(first_val, (dict, list, tuple)):
                 # - key: \n ...
                 # - key[N]: ...
                 # We can delegate to _encode_value but we need to trick it into writing to the same line?
                 # Easier to handle manually.
                 
                 # Check if first val is array headers
                 if isinstance(first_val, (list, tuple)):
                      # - key[N]: ...
                      # We buffer the sub-call? 
                      # Or we just manually format the header line?
                      # It's getting recursive.
                      pass
                      
            # Simplify: TOON list items for objects put the first field on the hyphen line.
            # "- key: value"
            # And subsequent fields at depth+1
            
            # Let's handle generic object dumping but intercept first line.
            # Hacky but works: dump the object to string at depth 0, 
            # then prepend "- " to first line, and indent subsequent lines.
            # But we need correct depth context.
            
            # Better:
            # Write "- "
            # Write first key/value pair.
            # Write remaining pairs at depth (relative to item).
            
            prefix = f"{indent}- "
            
            items = list(item.items())
            k1, v1 = items[0]
            
            # Hack: Encode the first value as if it was at depth 0 but we manage the prefix
            # This is complex because _encode_value writes indentation.
            
            # Let's do it manually
            encoded_k1 = self._format_key(k1)
            
            if isinstance(v1, dict):
                # Nested object
                buffer.write(f"{prefix}{encoded_k1}:{NEWLINE}")
                self._encode_object_fields(v1, buffer, depth + 1)
            elif isinstance(v1, (list, tuple)):
                # Array
                # - key[N]: ...
                # Use _encode_array but passing a flag or tricking buffer?
                # We can call _encode_array with key=k1.
                # But we need to prepend "- " to the first line it writes.
                # We can pass `prefix="- "` to _encode_array?
                pass
                
                # Let's use a temporary buffer for the first field
                temp = StringIO()
                self._encode_value(k1, v1, temp, 0)
                # content = "key: val\n" or "key[N]:...\n"
                # We want "- content" indented.
                # But `content` has depth 0 indentation (empty).
                
                content = temp.getvalue()
                # Split lines
                lines = content.splitlines(keepends=True)
                if not lines: return # Should not happen
                
                buffer.write(f"{prefix}{lines[0]}")
                # Subsequent lines need to be indented to match depth
                # Wait, if array is expanded, lines[1+] are items.
                # If array is inline, it's one line.
                
                # The depth of the array items should be relative to the list item?
                # Spec: "nested fields at depth +2 relative to the hyphen line" (Section B.5)
                # Wait, depth + 2 relative to hyphen?
                # Hyphen is at depth D. Indent.
                # First field is on hyphen line.
                # Sibling fields of the object are at depth D+1 (align with first field).
                # Children of first field are at depth D+2.
                
                # My _encode_value at depth 0 produces children at depth 1.
                # If I indent them by `depth + 1` relative to root...
                # Current depth is `depth`.
                # Prefix is `depth` indent.
                # Lines[1+] from temp (depth 0) have `indent_str * 1` etc.
                # I need to add `indent_str * depth` to them?
                # Yes.
                
                for line in lines[1:]:
                     buffer.write(f"{self._indent_str * depth}{line}")
                
            else:
                 # Primitive
                 enc_v1 = self._format_primitive(v1, self.delimiter)
                 buffer.write(f"{prefix}{encoded_k1}: {enc_v1}{NEWLINE}")

            # Remaining fields
            for k, v in items[1:]:
                # Sibling fields 
                self._encode_value(k, v, buffer, depth) # This adds `depth` indent which aligns with "- " start?
                # "- " is at `indent`.
                # "key:" is at `indent`. 
                # Wait, "- " takes space.
                # Spec:
                # - key: val
                #   key2: val2
                # Indentation of key2 should match key1?
                # "List items start with "- " at one deeper depth than parent... Items appear at depth+1"
                # "Object... first field on the hyphen line... nested fields at depth+1" -> Wait.
                # If first field is on hyphen line: "- key: val"
                # Sibling fields: "  key2: val2" (assuming 2 space indent)
                # So sibling fields are at `depth`.
                # Wait, "- " is 2 chars. If indent is 2 spaces.
                # key starts at col 2.
                # key2 starts at col 2 (indent 1 level).
                # So yes, sibling fields are at `depth` level indent.
                pass
                
        elif isinstance(item, (list, tuple)):
            # Nested array (List of Lists)
            # - [M]: ...
            # Call _encode_array logic?
            # expanded list item: "- [M]: ..."
            prefix = f"{indent}- "
            
            if self._is_primitive_array(item):
                 vals = [self._format_primitive(v, self.delimiter) for v in item]
                 line = self.delimiter.join(vals)
                 buffer.write(f"{prefix}[{len(item)}]: {line}{NEWLINE}")
            else:
                 # Array of arrays or objects mixed
                 # - [M]:
                 #   - ...
                 buffer.write(f"{prefix}[{len(item)}]:{NEWLINE}")
                 for sub in item:
                      self._encode_list_item(sub, buffer, depth + 1)
                      
        else:
            # Primitive
            # - value
            enc = self._format_primitive(item, self.delimiter)
            buffer.write(f"{indent}- {enc}{NEWLINE}")

    def _encode_root_array(self, arr: List[Any], buffer: TextIO):
        # [N]: ...
        # [N]{...}: ...
        self._encode_array(None, arr, buffer, 0)


    # Helpers
    def _is_primitive(self, v):
        return not isinstance(v, (dict, list, tuple))

    def _is_primitive_array(self, arr):
        return all(self._is_primitive(x) for x in arr)

    def _get_uniform_keys(self, arr) -> Optional[Tuple[str, ...]]:
        if not arr: return None
        if not all(isinstance(x, dict) for x in arr): return None
        
        # Must have same keys
        first_keys = tuple(arr[0].keys())
        # Check all values are primitives? Spec 9.3: "All values across these keys are primitives"
        for x in arr:
            if tuple(x.keys()) != first_keys: return None
            if not all(self._is_primitive(v) for v in x.values()): return None
            
        return first_keys

    def _format_key(self, key: str) -> str:
        # Check if needs quoting
        if RE_UNQUOTED_KEY.match(key):
            return key
        return self._format_string(key, active_delimiter=None, force_quote=True)

    def _format_primitive(self, val: Any, active_delimiter: str) -> str:
        if val is None: return "null"
        if isinstance(val, bool): return "true" if val else "false"
        if isinstance(val, (int, float)):
             # Check for inf/nan?
             return str(val)
        return self._format_string(str(val), active_delimiter)

    def _format_string(self, s: str, active_delimiter: Optional[str], force_quote: bool = False) -> str:
        # Check encoding rules Section 7.2
        needs_quote = force_quote
        
        if not needs_quote:
            if not s: needs_quote = True
            elif s[0] in ' -': needs_quote = True # Start with space or hyphen
            elif s[-1] in ' ': needs_quote = True # Trailing space
            elif s in ('true', 'false', 'null'): needs_quote = True
            elif RE_NUMERIC.match(s) or RE_LEADING_ZERO.match(s): needs_quote = True
            elif any(c in s for c in ':"\\{}[]'): needs_quote = True # Colon, quote, backslash, brackets
            elif any(c in s for c in '\n\r\t'): needs_quote = True # Control
            elif active_delimiter and active_delimiter in s: needs_quote = True
            
        if not needs_quote:
            return s
            
        # Quote and escape
        out = ['"']
        for c in s:
            if c in ESCAPE_MAP:
                out.append(ESCAPE_MAP[c])
            else:
                out.append(c) # Check for other control chars? Spec only says \n\r\t are valid escapes.
        out.append('"')
        return "".join(out)


def dumps(obj: Any, indent: int = 2) -> str:
    encoder = TOONEncoder(indent_size=indent)
    return encoder.encode(obj)

def dump(obj: Any, fp: TextIO, indent: int = 2):
    fp.write(dumps(obj, indent=indent))
