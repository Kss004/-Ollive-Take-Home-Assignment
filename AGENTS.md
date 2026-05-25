# Agent rules for this repo

## Docker / container runtimes — handoff, do not execute

Do **not** run `docker`, `docker compose`, `kubectl`, `kind`, or any other
container-runtime commands yourself. Instead, print the exact command(s) the
user should run in a fenced code block; the user executes them locally and
pastes the output back.

Applies to:
- building images (`docker compose build`, `docker build`)
- starting stacks (`docker compose up`, `docker compose up -d`)
- tailing logs (`docker compose logs -f`)
- restarting / killing services
- exec into containers (`docker compose exec`)
- k8s apply / get / port-forward

Still fine to run yourself:
- code edits, reads, greps
- `pytest`, `uv`, `bun` against the host
- `psql` / `redis-cli` from the host against an already-running container
- shell utilities that don't touch container runtimes

Rationale: saves tokens on long build/run output. The user can stream verbose
container logs to their terminal without round-tripping through the assistant.

## Tooling defaults

- Python: `uv` over `pip`.
- JS/TS: `bun` over `npm`.

## Style

- Caveman mode is on by default in this session. Code, commits, security
  warnings, and irreversible-action confirmations stay in normal prose.
