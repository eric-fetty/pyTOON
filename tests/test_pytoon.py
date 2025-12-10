import unittest
import sys
import os

# Ensure src is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from pytoon import dumps, loads, TOONDecodeError

class TestPyTOON(unittest.TestCase):
    def test_primitives(self):
        self.assertEqual(loads('true'), True)
        self.assertEqual(loads('false'), False)
        self.assertEqual(loads('null'), None)
        self.assertEqual(loads('42'), 42)
        self.assertEqual(loads('3.14'), 3.14)
        self.assertEqual(loads('"foo"'), "foo")
        self.assertEqual(loads('foo'), "foo") # Unquoted string

    def test_simple_object(self):
        obj = {"a": 1, "b": "foo"}
        encoded = dumps(obj)
        decoded = loads(encoded)
        self.assertEqual(decoded, obj)

    def test_nested_object(self):
        obj = {"user": {"name": "Alice", "age": 30}}
        encoded = dumps(obj)
        # Expected:
        # user:
        #   name: Alice
        #   age: 30
        decoded = loads(encoded)
        self.assertEqual(decoded, obj)

    def test_primitive_array(self):
        arr = [1, 2, 3]
        encoded = dumps(arr)
        # Expected: [3]: 1,2,3
        self.assertIn('[3]: 1,2,3', encoded)
        decoded = loads(encoded)
        self.assertEqual(decoded, arr)

    def test_tabular_array(self):
        arr = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"}
        ]
        encoded = dumps(arr)
        # Expected: 
        # [2]{id,name}:
        #   1,Alice
        #   2,Bob
        self.assertIn('{id,name}:', encoded)
        decoded = loads(encoded)
        # Note: dict order might vary, but TOONEncoder uses first object keys
        self.assertEqual(decoded, arr)

    def test_mixed_array(self):
        arr = [1, {"a": 2}]
        encoded = dumps(arr)
        # Expanded list
        # [2]:
        #   - 1
        #   - a: 2
        decoded = loads(encoded)
        self.assertEqual(decoded, arr)

    def test_spec_hikes_example(self):
        # From Spec/Readme
        # context: task: Our favorite hikes together location: Boulder season: spring_2025 friends[3]: ana,luis,sam hikes[3]{id,name,distanceKm,elevationGain,companion,wasSunny}: 1,Blue Lake Trail,7.5,320,ana,true 2,Ridge Overlook,9.2,540,luis,false 3,Wildflower Loop,5.1,180,sam,true
        
        toon = """
context:
  task: Our favorite hikes together
  location: Boulder
  season: spring_2025
friends[3]: ana,luis,sam
hikes[3]{id,name,distanceKm,elevationGain,companion,wasSunny}:
  1,Blue Lake Trail,7.5,320,ana,true
  2,Ridge Overlook,9.2,540,luis,false
  3,Wildflower Loop,5.1,180,sam,true
"""
        # Leading newline in triple quote string is empty?
        # Strip leading newline if present
        if toon.startswith('\n'): toon = toon[1:]
        
        data = loads(toon)
        
        self.assertEqual(data['friends'], ['ana', 'luis', 'sam'])
        self.assertEqual(data['hikes'][0]['name'], 'Blue Lake Trail')
        self.assertEqual(data['hikes'][1]['wasSunny'], False)
        
        # Round trip
        encoded = dumps(data)
        decoded = loads(encoded)
        self.assertEqual(decoded, data)

    def test_invalid_syntax(self):
        with self.assertRaises(TOONDecodeError):
             loads('"terminated') # Unterminated string

if __name__ == '__main__':
    unittest.main()
