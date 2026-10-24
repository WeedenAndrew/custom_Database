# Context — custom_Database

## Decisions (Andrew, 2026-10-23)

- "I was thinking of a custom private redis codebase to help with caching on
  top of our decalred key value store"
- "The redis style codebase will be locally hosted and a library type call,
  create custom_Database project in our projects folder to prepare for that"
- "the command ban is nitric up nothing will ever be pushed to the cloud
  unless needed"

What follows from them:
- **A library, not a server.** No Redis server process, no network protocol,
  no port. Rule 29 forbids connecting to a hand-run server, and GAN_ecc's
  gate blocks `redis.Redis(`.
- **Storage is a declared Nitric key-value store.** Nitric has no cache
  primitive (researched 2026-10-23, `Misc/IfC-Framework-Direction.md` in
  the journal). The key-value store does get, set, delete and query.
- **Expiry is this library's job.** Whether Nitric's key-value store
  supports a TTL is `[unverified]`. The working assumption is that each value
  is stored with its expiry time and checked on read.
- **Python.** It matches the Nitric Python SDK and GAN_ecc's pytest loop.
- **Local only.** `nitric run` and `nitric start` are fine. `nitric up` is
  never run by an agent unless Andrew asks for it and accepts it.

## Facts from the GAN_ecc spike (Nitric Python SDK 1.2.4, 2026-10-23)

Read from the SDK source, and run against a test double of the server. The
real-server run is pending.

- **The key-value API** is async `set(key, dict)`, `get(key) -> dict`,
  `delete(key)` and `keys(prefix)`. The permissions are `get`, `set` and
  `delete`. There is **no expiry**, so this library owns expiry.
- **Values must be dicts.** A plain string is rejected with
  `AttributeError`. **Numbers come back as floats** (`7` returns as `7.0`),
  and integers above 2^53 lose precision. So this library must encode
  values to keep their types, for example JSON inside a one-field dict.
- **A missing or deleted key raises `nitric.exception.NotFoundException`.**
- **Docker Desktop must be running** for `nitric start`, which always starts
  a local Postgres container, even when only a key-value store is declared.
  Andrew's first spike run failed on this.
- **Declaring connects at import.** Code that declares the store can only be
  imported where a Nitric server is reachable, so tests run inside
  `nitric start`.

## Open questions, for the DoD

- Which Redis-style operations the first version needs: for example get,
  set with expiry, delete, increment, expire, ttl, and keys by prefix.
- How tests run: against `nitric start`, or something else. The GAN-ecc-IfC
  spike answers whether pytest works against `nitric start` on Windows.
  Until then this is undecided. A hand-kept stand-in would break rule 29's
  "local runs use the same declarations".
- Key layout and namespaces when more than one project shares it.
- Size limits and eviction: none, a maximum count, or least-recently-used.
- Concurrency: what two writers to the same key should see.
- First user: likely `iaa_Profitability` (price lookups) `[unverified fit]`.

## Built — 2026-10-24

- **How it was built:** through GAN_ecc's loop, in two rounds (Andrew:
  "Through GAN_ecc's loop", "Core plus structures"). Both specs are in
  `GAN_ecc/harness/specs/`.
  - **Round 1, core:** clean, 109 tests. `quest/custom-database-core-20261024-021210`.
  - **Round 2, structures:** clean on the clarified spec.
    `quest/custom-database-structures-20261024-023025`.
- **Andrew's isolation requirement:** "they do not have colliding
  information and or the ability to peek into others information".
  - **Met in the library:** stored keys are collision-free, and no method
    reaches another namespace.
  - **The remaining wall:** code that holds the raw store is the
    orchestrator's to control. Models get no store access.
- **The spec clarification**, approved by Andrew: `set`'s `ttl=None` is the
  default and means no expiry; `expire` needs a number.
- **The held-out acceptance suite** was written from the specs, never shown
  to either agent, and checked to catch 5/5 planted mistakes. The published
  code passed 87/87 on the Nitric test double. The real-server run on
  Andrew's machine is the last proof.

## Not in scope until a DoD is signed

Writing code, picking dependencies, creating any cloud resource, and
deploying.
