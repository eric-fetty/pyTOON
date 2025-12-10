# pyTOON

Token-Oriented Object Notation (TOON) implementation for Python.

## Installation

```bash
pip install pytoon
```

## Usage

`pytoon` provides a familiar API similar to the built-in `json` module.

```python
import pytoon

data = {
    "name": "Toon World",
    "param": 42,
    "features": ["simple", "fast"]
}

# Serialize to string
toon_string = pytoon.dumps(data)
print(toon_string)

# Deserialize from string
loaded_data = pytoon.loads(toon_string)
print(loaded_data)
```

## License

MIT
