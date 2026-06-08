#!/usr/bin/env python3
"""
Build the hub's distributable artifacts from the source commands.

For every `commands/<slug>/` it:
  - parses `command.md` frontmatter (the SAME key:value rules MaplePet uses) + `hub.meta.json`,
  - validates the command (name / kind / per-kind payload / local image refs / hosts),
  - builds an install-ready zip `dist/commands/<slug>/<slug>-<version>.zip` whose single top-level folder
    is `<slug>/` (the shape the app's importer expects), with version/author/minAppVersion/tags injected
    into the zipped `command.md` so an installed command self-describes,
  - computes its sha256,
and finally writes `dist/index.json` (the registry the app reads) + `dist/latest.json`.

Usage:
  python tools/build_index.py            # build dist/
  python tools/build_index.py --check    # validate only (PR gate); non-zero exit on any error
"""
import os, sys, json, hashlib, zipfile

OWNER = "Leonana69"
REPO = "TypePet-Commands"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMANDS = os.path.join(ROOT, "commands")
DIST = os.path.join(ROOT, "dist")

KIND_ALIASES = {
    "text": "text", "say": "text",
    "clipboard": "clipboard", "copy": "clipboard",
    "image": "image", "img": "image",
    "link": "link", "url": "link",
    "prompt": "prompt", "llm": "prompt", "ai": "prompt",
    "pet": "pet", "action": "pet",
    "script": "script", "js": "script",
}
ASSET_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".md", ".json"}
FIXED_DT = (1980, 1, 1, 0, 0, 0)  # deterministic zip timestamps -> stable sha


def strip_quotes(v):
    if len(v) >= 2 and ((v[0] == '"' and v[-1] == '"') or (v[0] == "'" and v[-1] == "'")):
        return v[1:-1]
    return v


def parse_frontmatter(text):
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return None, text
    fm, i = {}, 1
    while i < len(lines) and lines[i].strip() != "---":
        line = lines[i].strip()
        i += 1
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        fm[k.strip().lower()] = strip_quotes(v.strip())
    if i >= len(lines):
        return None, text  # no closing ---
    body = "\n".join(lines[i + 1:]).strip("\n")
    return fm, body


def is_valid_host(h):
    return ("." in h and not h.startswith(".") and not h.endswith(".")
            and all(c.isalnum() or c in ".-" for c in h) and h.isascii())


def validate(slug, fm, body, cdir, meta, errors):
    if fm is None:
        errors.append(f"{slug}: command.md has no valid frontmatter"); return
    name = fm.get("name", "")
    if not name or len(name) > 32 or not all(c.isalnum() or c in "-_" for c in name):
        errors.append(f"{slug}: invalid or missing 'name'")
    raw_kind = (fm.get("kind") or "").lower()
    kind = KIND_ALIASES.get(raw_kind)
    if kind is None:
        errors.append(f"{slug}: unknown kind '{raw_kind}'"); return
    if kind == "clipboard" and not (fm.get("clipboard") or fm.get("copy")):
        errors.append(f"{slug}: clipboard kind needs a 'copy:' value")
    if kind == "link" and not fm.get("link"):
        errors.append(f"{slug}: link kind needs a 'link:' value")
    if kind in ("prompt", "script", "pet") and not body.strip():
        errors.append(f"{slug}: {kind} kind needs a body")
    img = fm.get("image")
    if kind == "image":
        if not img:
            errors.append(f"{slug}: image kind needs an 'image:' value")
        elif img.lower().startswith(("http://", "https://")):
            errors.append(f"{slug}: remote image URLs are not allowed — bundle the image in the command folder")
        elif ".." in img or img.startswith(("/", "\\")) or not os.path.isfile(os.path.join(cdir, img)):
            errors.append(f"{slug}: image '{img}' must be a local file inside the command folder")
    for h in [x.strip().lower() for x in (fm.get("hosts") or fm.get("host") or "").split(",") if x.strip()]:
        if not is_valid_host(h):
            errors.append(f"{slug}: invalid host '{h}' in hosts:")
    # assets allowlist + size cap
    total = 0
    for dp, _, fns in os.walk(cdir):
        for fn in fns:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in ASSET_EXTS:
                errors.append(f"{slug}: disallowed file type '{fn}'")
            total += os.path.getsize(os.path.join(dp, fn))
    if total > 2 * 1024 * 1024:
        errors.append(f"{slug}: command folder exceeds 2 MB")
    # hub.meta.json
    ver = str(meta.get("version", fm.get("version", "")))
    if not ver or not all(p.isdigit() for p in ver.split("-")[0].split("+")[0].split(".")):
        errors.append(f"{slug}: hub.meta.json needs a numeric semver 'version'")
    if not meta.get("author"):
        errors.append(f"{slug}: hub.meta.json needs an 'author'")


def inject_meta(cmd_text, fm, version, author, meta):
    lines = cmd_text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return cmd_text
    close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if close is None:
        return cmd_text
    ins = []
    if "version" not in fm: ins.append(f"version: {version}")
    if author and "author" not in fm: ins.append(f"author: {author}")
    mav = meta.get("minAppVersion") or meta.get("minappversion")
    if mav and "minappversion" not in fm and "minapp" not in fm: ins.append(f"minAppVersion: {mav}")
    tags = meta.get("tags")
    if tags and "tags" not in fm: ins.append("tags: " + ", ".join(tags))
    if not ins:
        return cmd_text
    return "\n".join(lines[:close] + ins + lines[close:])


def add_entry(z, arcname, data):
    zi = zipfile.ZipInfo(arcname, date_time=FIXED_DT)
    zi.compress_type = zipfile.ZIP_DEFLATED
    zi.external_attr = 0o644 << 16
    z.writestr(zi, data)


def make_zip(cdir, slug, injected_cmd, zip_abs):
    rels = []
    for dp, _, fns in os.walk(cdir):
        for fn in fns:
            rel = os.path.relpath(os.path.join(dp, fn), cdir).replace("\\", "/")
            if rel == "hub.meta.json":
                continue
            rels.append(rel)
    rels.sort()
    os.makedirs(os.path.dirname(zip_abs), exist_ok=True)
    if os.path.exists(zip_abs):
        os.remove(zip_abs)
    with zipfile.ZipFile(zip_abs, "w") as z:
        for rel in rels:
            if rel == "command.md":
                add_entry(z, f"{slug}/command.md", injected_cmd.encode("utf-8"))
            else:
                with open(os.path.join(cdir, rel), "rb") as f:
                    add_entry(z, f"{slug}/{rel}", f.read())


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    check_only = "--check" in sys.argv
    slugs = sorted(d for d in os.listdir(COMMANDS)
                   if os.path.isdir(os.path.join(COMMANDS, d))) if os.path.isdir(COMMANDS) else []
    errors, entries = [], []

    for slug in slugs:
        cdir = os.path.join(COMMANDS, slug)
        cmd_path = os.path.join(cdir, "command.md")
        if not os.path.isfile(cmd_path):
            continue
        with open(cmd_path, encoding="utf-8") as f:
            cmd_text = f.read()
        fm, body = parse_frontmatter(cmd_text)
        meta = {}
        mp = os.path.join(cdir, "hub.meta.json")
        if os.path.isfile(mp):
            try:
                with open(mp, encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception as e:
                errors.append(f"{slug}: hub.meta.json is invalid JSON ({e})")
        if not os.path.isfile(mp):
            errors.append(f"{slug}: missing hub.meta.json")

        validate(slug, fm, body, cdir, meta, errors)
        if check_only or fm is None:
            continue

        name = fm.get("name", slug)
        kind = KIND_ALIASES.get((fm.get("kind") or "").lower(), "")
        hosts = [h.strip().lower() for h in (fm.get("hosts") or fm.get("host") or "").split(",") if h.strip()]
        version = str(meta.get("version", fm.get("version", "1.0.0")))
        author = meta.get("author", "")
        mav = meta.get("minAppVersion") or meta.get("minappversion")

        injected = inject_meta(cmd_text, fm, version, author, meta)
        zip_rel = f"commands/{slug}/{slug}-{version}.zip"
        zip_abs = os.path.join(DIST, zip_rel)
        make_zip(cdir, slug, injected, zip_abs)

        entries.append({
            "id": slug,
            "name": name,
            "title": meta.get("title", name),
            "version": version,
            "author": author,
            "license": meta.get("license", "GPL-3.0-or-later"),
            "description": fm.get("help", fm.get("description", "")),
            "kind": kind,
            "tags": meta.get("tags", []),
            "minAppVersion": mav,
            "requiresScripting": kind == "script",
            "requiresNetwork": len(hosts) > 0,
            "requiresChat": kind == "prompt",
            "hosts": hosts,
            "official": bool(meta.get("official", False)),
            "verified": True,
            "updated": meta.get("updated"),
            "repoPath": f"commands/{slug}",
            "download": {
                "url": f"https://cdn.jsdelivr.net/gh/{OWNER}/{REPO}@main/dist/{zip_rel}",
                "bytes": os.path.getsize(zip_abs),
                "sha256": sha256_file(zip_abs),
                "fallbackUrl": f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/dist/{zip_rel}",
            },
        })
        print(f"  built {slug} v{version} [{kind}]")

    if errors:
        print("VALIDATION ERRORS:", file=sys.stderr)
        for e in errors:
            print("  - " + e, file=sys.stderr)
        sys.exit(1)

    if check_only:
        print(f"OK: {len(slugs)} command(s) valid.")
        return

    entries.sort(key=lambda e: e["id"])
    os.makedirs(DIST, exist_ok=True)
    # No timestamp here on purpose: the output must be byte-deterministic so a re-run with unchanged source
    # produces an identical index.json. Otherwise the CI publish would see a "change" every run and commit a
    # regenerated dist back to main, putting the remote ahead and forcing a pull/merge on the next push.
    index = {
        "schemaVersion": 1,
        "indexTag": "main",
        "commands": entries,
    }
    with open(os.path.join(DIST, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
        f.write("\n")
    with open(os.path.join(DIST, "latest.json"), "w", encoding="utf-8") as f:
        json.dump({"indexTag": "main", "minClientForIndex": "1.0.0"}, f, indent=2)
        f.write("\n")
    print(f"Wrote dist/index.json ({len(entries)} commands).")


if __name__ == "__main__":
    main()
