# Contributing

Open an engineering issue with acceptance evidence before changing a model. Use a focused
branch and pull request; link the issue and any ADR. Preserve the canonical scenarios and
published evidence unless an explicitly reviewed model change requires a new benchmark version.

```sh
python -m pip install -e ".[dev]"
python -m pip check
python -m ruff check .
python -m mypy
python -m pytest
python scripts/check_evidence.py
python -m build
```

CI runs Python 3.11/3.12, independent orbit comparisons, canonical evidence reproduction,
wheel installation outside the checkout, and a Docker HTTP/AppTest smoke. A green badge is
bounded evidence; it does not establish physical model truth or a live deployment.

For `main`, require a PR, current-branch checks named `Python 3.11`, `Python 3.12`, and
`Docker smoke`, resolved conversations, and disable force pushes/deletion. Require zero
external approvals for this solo-maintainer repository so it remains usable without pretending
an independent reviewer exists. The maintainer still reviews the diff and evidence before merge.
Describe the applied protection status in [status](docs/status.md); this file alone does not
enforce repository settings.

Do not put real medical data, credentials, local machine paths, or private application materials
in issues, logs, fixtures, or PRs. See [AI assistance](docs/ai-assisted-development.md).
