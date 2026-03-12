---
name: lint
description: Run all CI linters locally (yamllint, ansible-lint, shellcheck, hadolint, markdownlint, tclint)
---

Check that each linter is installed before running it (`command -v <tool>`).
Run all linters that are present regardless of which are missing — do not stop early.
For any missing tool, note it in the summary and tell the user to follow the
Dev Prerequisites section in CONTRIBUTING.md — do not attempt to install them.

Run each available tool:

1. `yamllint .`
2. `ansible-lint`
3. `shellcheck setup.sh services/*/entrypoint.sh`
4. `markdownlint '**/*.md'`
5. `tclint shared/tcl-scripts/*.tcl`

Report a pass/fail/missing summary at the end. For failures, show errors and offer to fix them.
