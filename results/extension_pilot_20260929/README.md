# Retained exploratory structural evidence

`run-001` contains the completed 2026-09-29 structural pilot, not a completed
timing experiment. Keep its files unchanged. Its manifest is STRUCTURAL_PASS.

The executed source is `structural_source.py`. `structural_protocol.md` was
recovered on 2026-10-20 by removing the explicitly later pre-timing clarification
from the current protocol; its bytes exactly match the original SHA-256 already
recorded by the 2026-09-29 invocation. This is recovery of the frozen text, not a
new preregistration. The current protocol and user-run addendum live in `docs/`.

Git attributes disable newline conversion for this evidence so byte hashes are
portable. The new continuation runner uses a separately named output root and
does not mutate the original invocation. `historical_audit.json` references local
Experiment 1 data for provenance; those large files are not required by the new
runner or included in this package.
