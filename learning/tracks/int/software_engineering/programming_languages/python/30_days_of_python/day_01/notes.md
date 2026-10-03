Day 1 — Python Basics

- Python runs two ways: interactive shell, or a saved .py script file.
- Indentation is not style in Python — it's how code blocks are defined.
  Other languages use {}, Python uses whitespace. Wrong indentation = broken code.
- Comments: # for one line. Triple-quoted string (not assigned to a variable)
  for multi-line.

Data types:
- int / float / complex — the three number types. Complex is written like 1 + 3j.
- string — text in ' ' or " ", or triple quotes if it spans multiple lines.
- boolean — True or False only, always capitalised.
- list — ordered, can mix types, can change after creation. [1, 2, 'x']
- dict — key:value pairs, unordered. {'name': 'x', 'age': 1}
- tuple — ordered like a list, but locked once created (immutable).
- set — unordered, and only keeps unique values (duplicates collapse).

type(x) tells you what type something is — this is the tool for checking,
not guessing from how a value looks.

Operators covered: + - * / ** (power) % (modulus/remainder) // (floor division,
drops the decimal instead of rounding).

