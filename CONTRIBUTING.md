# Contributing a command

Thanks for sharing a command! Everything is reviewed before it's published to all users.

## What a command looks like

One folder per command under `commands/<slug>/`:

- **`command.md`** — frontmatter (`---` key: value `---`) + a body. Exactly the format MaplePet parses.
- **`hub.meta.json`** — hub-only metadata.
- Optional small **images** (`.png/.jpg/.gif/.webp`) referenced by a `kind: image` command, co-located
  in the folder. Remote `image:` URLs are **not** allowed — bundle the image.

`<slug>` must be lowercase `[a-z0-9-]`, and match the command's `name:`.

### `command.md`

```markdown
---
name: roll
kind: script        # text | clipboard | image | link | prompt | pet | script
usage: /roll [sides]
help: Roll a die (default 6 sides).
holdSeconds: 8
# script commands that need the network must declare the hosts they reach:
# hosts: example.com, api.example.com
---
var n = 1 + Math.floor(Math.random() * 6);
say("You rolled a " + n + "!");
```

### `hub.meta.json`

```json
{
  "title": "Dice Roll",
  "version": "1.0.0",
  "author": "your-github-username",
  "license": "GPL-3.0-or-later",
  "tags": ["fun", "rng"],
  "minAppVersion": "1.0.0",
  "official": false
}
```

- **`version`** is semver. **Bump it on every change** to an existing command (CI enforces this).
- **`author`** is overwritten with your verified GitHub login on merge — don't claim someone else's.
- **`minAppVersion`** is the lowest MaplePet version that can run it. Use a newer kind/script API → set
  it to the version that added that capability (see [`app-compat/supported.json`](app-compat/supported.json)).

## Rules (CI checks these)

- Valid `name` + known `kind` + the payload that kind needs (e.g. `clipboard` needs `copy:`).
- `image:` must be a local file inside the folder — no remote URLs.
- `hosts:` entries must be bare hostnames; **scripts reach only the hosts they declare, over HTTPS**, and
  only after the user approves them. Keep the list minimal and justified.
- Folder ≤ 2 MB; only `.md/.json` + image files.
- Don't edit `dist/` — it's generated.

## Content policy

- **No MapleStory / Nexon assets** (sprites, UI, music) and no links to private/pirate servers.
- Clipboard text should be emoji-free (MapleStory chat strips Unicode emoji).
- By submitting, you assert the command is your own work (or appropriately licensed) under GPL-3.0-or-later.

## Test locally

```bash
python tools/build_index.py --check   # validate
python tools/build_index.py           # build dist/ to inspect
```

Then open a PR. The maintainer reviews it (script bodies especially) and merges; CI regenerates the
registry and your command appears in the app's **Browse hub** tab.
