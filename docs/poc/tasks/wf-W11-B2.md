# 不具合の報告（pytest）

このリポジトリ（pytest）に、利用者から次の Issue が報告されています。原因を調べて修正してください。

---

# Walrus expression duplicate evaluation failures with rewrite

When we upgraded pytest from 7.2.0 -> 9.0.3, test failures appeared due to our use of walrus operators (`:=`) within `assert` statements. I have narrowed and reproduced this in `test_walrus.py` below. These two failing tests will _pass_ if we add `PYTEST_DONT_REWRITE` to the docstring, or run `pytest --assert=plain test_walrus.py`.

```python
"""
Minimal reproducer: pytest 9.0.3 assertion rewriting evaluates walrus operator (:=) twice.
    pytest /tmp/test_walrus.py          # FAILS
    pytest /tmp/test_walrus.py --assert=plain  # PASSES
"""

class Counter:
    def __init__(self):
        self.value = 0

    def increment(self):
        self.value += 1


def test_walrus_in_assertion_basic():
    """Walrus captures wrong value: rewriter evaluates := twice."""
    c = Counter()
    assert (before := c.value) == 0
    c.increment()
    assert before != (after := c.value)


def test_walrus_running_counter():
    """Cumulative walrus increments fire twice each → count doubles."""
    count = 0
    items = []
    items.append("a")
    assert (count := count + 1) == len(items)  # count becomes 2, not 1
    items.append("b")
    assert (count := count + 1) == len(items)  # count becomes 4, not 2
    items.append("c")
    assert (count := count + 1) == len(items)  # count becomes 6, not 3
    assert count == 3  # fails: count is 6
```

- [x] a detailed description of the bug or problem you are having
- [x] output of `pip list` from the virtual environment you are using
- [x] pytest and operating system versions
- [x] minimal example if possible

```
% python --version
Python 3.13.3
 % pip list
Package   Version
--------- -------
iniconfig 2.3.0
packaging 26.2
pip       25.0.1
pluggy    1.6.0
Pygments  2.20.0
pytest    9.0.3
```

I suspect related changes are https://github.com/pytest-dev/pytest/pull/10758 and https://github.com/pytest-dev/pytest/pull/11041
