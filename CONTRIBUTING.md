# Contributing

Issues and pull requests are welcome.

## Dev

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

ffmpeg must be on `PATH` for the mux tests.

## Rules

- Do not add DRM stripping, credential files, or personal hostnames.
- Keep `.env` out of git. `.env.example` stays placeholder-only.
- Prefer a failing test when you change extract, chunking, publish, or cost estimates.
