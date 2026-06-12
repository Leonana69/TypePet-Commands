# TypePet-Commands

The community **command hub** for [TypePet](https://github.com/Leonana69/TypePet) — the desktop pet.
Browse and one-click install these commands from inside the app (tray → **Browse hub…**).

A "command" is a small slash-command for the pet (e.g. `/roll`, `/symbols`). Each lives in one folder
under [`commands/`](commands/) as a `command.md` (frontmatter + body) plus a `hub.meta.json`. The app's
CI generates the registry the app reads (`dist/index.json`) and one install-ready zip per command.

## Install a command

In TypePet: tray icon → **Browse hub…**, find a command, click **Install**. Script commands install
**disabled** and request network access only after you approve it — review them first.

## Publish a command

Two ways — both go through a pull request the maintainer reviews before it's published to everyone:

- **From the app (easiest):** open the **Commands** tab, right-click your command → **Submit to hub…**.
  The app signs you in to GitHub (device flow) and opens a PR as you, automatically.
- **By hand:** fork this repo, add `commands/<slug>/` (`command.md` + `hub.meta.json` + any small local
  images), and open a PR. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Layout

```
commands/<slug>/command.md        # the command (same format the app parses)
commands/<slug>/hub.meta.json     # hub metadata: author, version, license, tags, minAppVersion, title
schema/command.schema.json        # JSON schema for hub.meta.json (CI validates against it)
app-compat/supported.json         # which kinds/script-APIs each app version supports
dist/                             # GENERATED — never hand-edit (index.json + per-command zips)
tools/build_index.py              # the generator CI runs
```

Everything in `dist/` is produced by `tools/build_index.py` and committed alongside the source (the build
is byte-deterministic). Don't edit it by hand — run the script. CI verifies `dist/` is up to date on every
push and fails if it's stale; it never rewrites `dist/` itself, so the remote never gets ahead of you.

## License

Commands are distributed under [GPL-3.0-or-later](LICENSE), matching TypePet. By submitting a command
you assert it is your own work (or appropriately licensed) and grant distribution here. No MapleStory /
Nexon assets, no links to private servers — see [CONTRIBUTING.md](CONTRIBUTING.md).
