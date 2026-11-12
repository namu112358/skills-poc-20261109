# 不具合の報告（pytest）

このリポジトリ（pytest）に、利用者から次の Issue が報告されています。原因を調べて修正してください。

---

# Error collecting tests on 9.1.1 - fixtures not found when a parent directory appears multiple times in a argument list 

_Disclosure: I have used AI to investigate this issue but am able to reproduce everything locally._

In Home Assistant, we tried to upgrade from PyTest 9.0.3 to 9.1.1 in https://github.com/home-assistant/core/pull/174371 (some diagnosis in comments)

We first ran into a collection abort issue in 9.1.0 that got fixed in 9.1.1 with https://github.com/pytest-dev/pytest/issues/14591.

With 9.1.1 we're hitting a new issue when collecting tests.

```
――――――――――――――― ERROR collecting tests/components/tts/test_init.py ―――――――――――――――
In tests/components/tts/test_init.py::test_setup_component_no_access_cache_folder: function uses no argument 'init_tts_cache_dir_side_effect'
```

I / Claude were not able to get a reproduction going outside of HA, so to reproduce you need to set up a HA dev env.

Step 1: Get a Home Assistant dev environment.

```
gh repo clone home-assistant/core
cd core
script/setup
```

```
> uv pip freeze | grep pytest
pytest==9.0.3
...
```

Step 2: Test collection passes

```
pytest --collect-only \
  tests/components/water_heater \
  tests/test_config_entries.py \
  tests/components/tts/test_init.py
```

Step 3: upgrade to pytest 9.1.1

```
uv pip install pytest==9.1.1
```

Step 4: Test collection fails

```
❯ uv pip install pytest==9.1.1
Resolved 5 packages in 97ms
Uninstalled 1 package in 15ms
Installed 1 package in 9ms
 - pytest==9.0.3
 + pytest==9.1.1
❯ pytest --collect-only \
  tests/components/water_heater \
  tests/test_config_entries.py \
  tests/components/tts/test_init.py
Test session starts (platform: darwin, Python 3.14.5, pytest 9.1.1, pytest-sugar 1.1.1)
rootdir: /Users/paulus/dev/hass/core
configfile: pyproject.toml
plugins: syrupy-5.3.2, pytest_freezer-0.4.9, socket-0.8.0, unordered-0.7.0, cov-7.1.0, xdist-3.8.0, typeguard-4.5.2, timeout-2.4.0, asyncio-1.4.0, github-actions-annotate-failures-0.4.0, aiohttp-1.1.1, sugar-1.1.1, rerunfailures-16.0.1, respx-0.23.1, picked-0.5.1, requests-mock-1.12.1, anyio-4.13.0
asyncio: mode=Mode.AUTO, debug=True, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collecting 3564 items                                                            
――――――――――――――― ERROR collecting tests/components/tts/test_init.py ―――――――――――――――
In tests/components/tts/test_init.py::test_setup_component_no_access_cache_folder: function uses no argument 'init_tts_cache_dir_side_effect'
collected 3564 items / 1 error  
```

Expand below to get a more elaborate AI generated description of the issue

<details>
<summary>AI generated diagnosis</summary>

### Description

In pytest 9.1 (both 9.1.0 and 9.1.1), the computed fixture closure of a test can change depending on **which unrelated paths were collected before it**. When a test relies on *implicit indirect* parametrization — `@pytest.mark.parametrize("some_fixture", [...])` where the test depends on `some_fixture` only transitively, not as a direct argument — collecting certain unrelated directories first causes that fixture to drop out of the closure, and collection fails with:

```
function uses no argument 'some_fixture'
```

The same test collects fine when run on its own, or when the other paths are collected in a different order. This passes on 9.0.3 and fails on 9.1.x, so it's a regression. I believe it is related to the fixture override-precedence rework (#14513 / PR #14566), which changed override ordering from registration-order to visibility/scope-order.

A test's fixture closure should be independent of what unrelated paths were collected earlier in the session.

### Reproduction

This reproduces against the public Home Assistant repo (the fixture graph that triggers it is non-trivial; I have not yet reduced it to a standalone `conftest.py`, but the repro below is fully deterministic and takes three commands):

```bash
git clone https://github.com/home-assistant/core hass-core
cd hass-core
git checkout 957c24fcd724          # any recent dev commit works
python -m venv venv && . venv/bin/activate
pip install -r requirements_test.txt -r requirements.txt   # or: pip install -e . pytest-aiohttp syrupy ...
pip install pytest==9.1.1

# Order matters. This fails:
pytest --collect-only \
  tests/components/water_heater \
  tests/test_config_entries.py \
  tests/components/tts/test_init.py
```

**Actual (9.1.1):**

```
ERROR collecting tests/components/tts/test_init.py
In tests/components/tts/test_init.py::test_setup_component_no_access_cache_folder: function uses no argument 'init_tts_cache_dir_side_effect'
!!! Interrupted: 1 error during collection !!!
```

**Expected (and actual on 9.0.3):** clean collection, ~3.6k tests collected, no error.

Notes on determinism:
- Deterministic across `PYTHONHASHSEED` (fails on random seeds and on fixed seeds 0–5).
- The failing file passes in isolation: `pytest --collect-only tests/components/tts/test_init.py` ✅.
- Reversing the order (e.g. collecting `tts` first) also passes — it is purely the order in which the earlier paths are collected.
- `--collect-only` is enough; no xdist required (we originally hit it under `-n auto --dist=loadfile`, but it's not xdist-specific).

### Why the test is structured this way (for context)

`tests/components/tts/test_init.py::test_setup_component_no_access_cache_folder`:

```python
@pytest.mark.parametrize("init_tts_cache_dir_side_effect", [OSError(2, "No access")])
@pytest.mark.parametrize("setup", ["mock_setup", "mock_config_entry_setup"], indirect=True)
async def test_setup_component_no_access_cache_folder(
    hass, mock_tts_init_cache_dir, setup
):
    ...
```

The closure that makes the `init_tts_cache_dir_side_effect` parametrize valid:

- the test directly requests `mock_tts_init_cache_dir` (in `tests/components/conftest.py`)
- `mock_tts_init_cache_dir` → requests `init_tts_cache_dir_side_effect` (also `tests/components/conftest.py`)
- additionally, `tests/components/tts/conftest.py` has an **autouse fixture that overrides a parent fixture and requests the same-named super**:
  ```python
  @pytest.fixture(autouse=True, name="mock_tts_cache_dir")
  def mock_tts_cache_dir_fixture_autouse(mock_tts_cache_dir):  # requests the parent of the same name
      return mock_tts_cache_dir
  ```
  whose parent (`tests/components/conftest.py`) transitively also reaches `init_tts_cache_dir_side_effect`.

Under 9.1 with a triggering prefix, `init_tts_cache_dir_side_effect` is no longer present in the closure, even though `mock_tts_init_cache_dir` is still requested directly — which is what makes this look like a closure-computation bug tied to the new override ordering rather than intended behavior.

### Environment

- pytest 9.1.1 (also reproduces on 9.1.0); **last known good: 9.0.3**
- pluggy 1.6.0
- Python 3.14.5
- macOS (Darwin arm64); also seen on Linux CI (Python 3.14.5)

### Suspected cause

#14513 / PR #14566 — fixture override ordering changed from registration-order to visibility-order. The order-dependence of the closure is the smell: with the new ordering, resolving an overridden fixture for the tts test appears to pick a fixturedef that no longer carries the `init_tts_cache_dir_side_effect` dependency, depending on what was registered while collecting earlier paths.

### Related

- #14591 — separate 9.1.0 regression ("duplicate parametrization of '<arg>'" when a fixture has `params=` and a test re-parametrizes it with `indirect=True`), fixed in 9.1.1. This report is a *different* problem that 9.1.1 does not fix.

</details>
