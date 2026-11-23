# Working in this repository

Use synthetic content only. Follow [CONTRIBUTING.md](CONTRIBUTING.md) for content and provenance rules.
Follow CONTRIBUTING.md's claim and accountability rules before starting or submitting work.
Expected values come from independent intents, never from a program's saved output.

Regeneration launches desktop CAD programs and can run a long time. Run it in the
foreground and wait for it to finish. It never commits, pushes, or runs network git commands.

Coverage ([COVERAGE.md](COVERAGE.md)), the map, and `results/` are generated artifacts.
Never edit them by hand; update their sources and regenerate them.

Compute the content digest on the drawing as read, before any audit. An audit can change
in-memory structure even when it reports no fixes. See [checker/VOLATILE.md](checker/VOLATILE.md).

Before proposing a change, run these checks from the repository root with the pinned dependencies:

```sh
python intent/validate.py
python -m pytest tests -q
python map/check_links.py
python checker/verify.py
```

The verification script includes regeneration, so it also requires the configured CAD programs
and must run in the foreground until it finishes.
