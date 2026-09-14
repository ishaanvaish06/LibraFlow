# Contributing to LibraFlow

## Local setup

```bash
git clone <repo-url> && cd LibraFlow
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
python -m pytest tests/ -q                        # should pass in ~4 seconds
```

## Code conventions

- **Style:** Standard library + type hints. No auto-formatter is enforced;
  follow the patterns already in the file you are editing.
- **No emojis** in source or test output.
- **No file in `libflow/api/` exceeds ~120 lines.** If a router is growing,
  extract helper functions or split into sub-modules.
- **Docstrings:** Every public module and class gets a one-line or short
  docstring. Internal helpers do not need one unless the intent is
  non-obvious.
- **Domain exceptions:** Services raise `libflow.core.exceptions.*`.
  The `app.py` handler maps them to HTTP codes. Never raise
  `HTTPException` from service or core code.

## Adding a new repository method

1. Add the method signature to the abstract contract in
   `libflow/storage/repository.py`.
2. Implement in `InMemoryBookRepository` (and siblings).
3. Implement in the `Postgres*Repository` class.
4. Write a unit test in `tests/` (in-memory path).
5. If the operation involves a write lock, add a concurrency test.

## Adding a new API endpoint

1. Add request/response schemas to `libflow/api/schemas.py`.
2. Write the route in the appropriate `libflow/api/routers/*.py`.
3. Wire dependencies through `libflow/api/dependencies.py` (never use
   module-level singletons in the router).
4. Add permission strings to the relevant role's `get_permissions()` set
   in `libflow/core/user.py`.
5. Write an API test in `tests/test_api.py` using the `client` fixture.

## Running tests

```bash
python -m pytest tests/ -q                                          # unit suite
python -m pytest tests/ --cov=libflow.core --cov=libflow.patterns \  # coverage
    --cov=libflow.dsa --cov-report=term --cov-config=pyproject.toml
docker compose -f docker-compose.test.yml up --abort-on-container-exit  # integration
```

## Commits

One clean commit at the end of a feature branch. Write a concise message
that matches the repo style (imperative mood, < 72 characters).

## Plan decisions

Implementation choices documented in `docs/DECISIONS.md` are final within
a feature branch. If a decision should change, update DECISIONS.md as
part of the same commit.
