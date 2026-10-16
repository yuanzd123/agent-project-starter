# Agent Project Starter

This repository contains a portable project-initialization prompt and a Python standard-library starter kit.

- Read README.md for usage and design boundaries.
- The deliverable is BOOTSTRAP_PROMPT.md plus template/. Keep the prompt usable without this repository.
- Run `python3 -m unittest discover -s tests -v` after changing executable behavior.
- Run `python3 template/scripts/memory.py check` after changing template memory.
- Keep source-project names, people, credentials, machine paths, raw history, and local audit notes out of distributable files. Local audit notes belong in ignored .local/.
- Public release and an open-source launch were authorized by the owner on 2026-10-15. This repository uses MIT. Keep releases scoped to this repository; the starter grants no deployment or data access authority to projects using it.
- English is the default documentation and template language. Keep the Chinese prompt, README and locale semantically aligned. Runtime code has one source under template/.
- Validate translations with `python3 tools/check_locales.py`. Run the executable demo with `python3 tools/demo.py`.
