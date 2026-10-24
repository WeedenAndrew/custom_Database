# Agent rules — custom_Database

- **`custom_database/_cache.py` is built by GAN_ecc's loop.** Never edit it
  by hand. A change means a new or changed spec in
  `GAN_ecc/harness/specs/`, approved by Andrew, then a round, the Quest, a
  merge, and a copy here byte for byte. The DoD is in the engineering
  journal, at `Projects/custom_Database.md`.
- **It is a library called in-process.** Never add a server, a port or a
  network protocol.
- **Tests run inside `nitric start`:** `python tools/nitric_pytest.py`. Run
  them before claiming anything works.
- Keep decisions in `CONTEXT.md`. Mark anything not checked as
  `[unverified]` in the same sentence.

<!-- rule-29:infrastructure-from-code -->
## Infrastructure from code (rule 29 — binds every agent that writes code here)

- Every database, queue or topic, scheduled job, file store, cache, secret
  and API endpoint the code uses is **declared in the application's own
  code**, next to where it is used, through the project's
  infrastructure-from-code framework (Nitric). There are no separate
  infrastructure files, and nothing is created by hand in a cloud console.
- **Here:** the only infrastructure is `kv("custom-database")`, declared in
  `_cache.py`. The cache itself is code, not infrastructure.
- **If it isn't declared in code, it doesn't exist.** Don't add a resource
  the task didn't ask for.
- Local runs use the same declarations, not a hand-kept stand-in.
- A setting the framework can't express is set at environment level, with a
  one-line reason in the project note. It is never changed silently.
- **Removing a declaration that holds data can destroy the data.** Ask
  first, and confirm a backup exists.
- **Never run `nitric up`.** It deploys to a cloud and starts billing.
  Nothing is deployed unless Andrew explicitly asks for it in chat and
  accepts it. Local `nitric run` and `nitric start` are fine.
