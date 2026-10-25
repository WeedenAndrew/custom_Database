# custom_Database

A **private, Redis-style cache library** in Python, run locally and used
through ordinary calls, **never a server**. It stores its data in one
**declared Nitric key-value store**, `custom-database`, following rule 29
(infrastructure from code).

It was **built by GAN_ecc's loop**:
- the specs are `GAN_ecc/harness/specs/custom-database-{core,structures}/`;
- the published rounds are `quest/custom-database-core-20261024-021210` and
  `quest/custom-database-structures-20261024-023025`;
- `custom_database/_cache.py` is the structures round's code, byte for byte
  (md5 `9ff7cee6…`).

## Use it

```python
import asyncio

LOOP = asyncio.new_event_loop()          # make the loop and set it BEFORE importing the library:
asyncio.set_event_loop(LOOP)             # the Nitric SDK picks up this loop when it is imported

from custom_database import Cache
cache = Cache("docs-chat")                # one handle = one namespace

LOOP.run_until_complete(cache.set("price:VIN123", 4200, ttl=3600))
LOOP.run_until_complete(cache.get("price:VIN123"))      # -> 4200 (an int, not 4200.0)
```

Code that imports it has to run under `nitric start`, because declaring
the store connects to the Nitric server at import. `nitric up` is banned.

## API (every method is a coroutine)

| method | returns |
|---|---|
| `get(key)` | the value, with its exact type; `None` if missing or expired |
| `set(key, value, ttl=None)` | `None`. `ttl` > 0 seconds sets an expiry; leaving it out (`None`) means no expiry and clears an earlier one |
| `delete(key)` | `True` if a live key was removed |
| `incr(key, by=1)` | the new int. A missing key counts as `0`; an existing expiry is kept |
| `expire(key, ttl)` | `True`, or `False` if the key is missing |
| `ttl(key)` | seconds left; `-1.0` means no expiry, `-2.0` means missing |
| `keys(prefix="")` | sorted live keys of this namespace |
| `hset / hget / hdel / hgetall / hkeys` | a hash (field → value) under one key |
| `lpush / rpush / lpop / rpop / lrange / llen` | a list under one key; `lrange` is inclusive, as in Redis |

- **Values:** `str`, `int` (any size), `float` (finite), `bool`, `list` and
  `dict` (with `str` keys), nested. They come back with exactly the same
  types. `None` can't be stored.
- **One type per key.** Using a key as a different kind raises
  `ValueError`. An emptied hash or list deletes its key. Expiry is checked
  whenever a key is read.

## Isolation

- **Namespaces never collide.** Stored keys are hex-encoded, so namespace
  `a` + key `b:c` and namespace `a:b` + key `c` are separate entries.
- **No method reaches another namespace's data.**
- **The library can't stop code that holds the raw store.** That wall is
  the orchestrator's: models get no store access, only the data for their
  own namespace.

## Limits

- **Single process:** `incr` reads and then writes, and the store has no
  compare-and-set.
- No sets, sorted sets or pub/sub.
- No eviction.

## Test it, inside `nitric start` (Docker Desktop must be running)

```powershell
cd C:\Users\andre\Desktop\projects\custom_Database
python tools\nitric_pytest.py
```

The runner makes `tools\.venv-nitric` (Python 3.11–3.13, `nitric==1.2.4`)
on the first run. It runs each test in its own process with a 60-second
limit and writes `report.xml`. The suite in `tests/` is the **acceptance
suite that was held out of both rounds**: neither agent ever saw it.
