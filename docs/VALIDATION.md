# Validation evidence

Run on 2026-11-20 with Python 3.11.7 on macOS ARM64.

- `ruff check .`: passed.
- `pytest -q`: **21 passed**. One upstream Starlette/AnyIO deprecation warning; no test failures.
- HTTP smoke test against a running Uvicorn server: simulator created 12 events (201), then replayed the same 12 IDs (200, duplicate=true).
- Browser check: connected with local API key, generated 12 events, filtered critical events, acknowledged one; critical/open changed from 2 to 1 and the acknowledged row remained visible.
- Screenshot: `docs/dashboard.jpg` shows this browser-verified state.

Docker and GitHub CI results are recorded below when verified. These checks establish functional behavior for a prototype, not production throughput, AI accuracy, fault tolerance, or security certification.

- GitHub Actions: not activated. Publishing credential lacks `workflow` scope; workflow is supplied as `docs/ci/github-actions.yml` for manual activation.
