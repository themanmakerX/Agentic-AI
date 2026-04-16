# Development Notes

## Principles

- Keep the graph local and inspectable.
- Prefer deterministic behavior.
- Document every user-facing workflow in English.

## Local Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

## Directory Layout

- `code_review_graph/` - runtime package
- `docs/` - documentation
- `tests/` - automated tests

