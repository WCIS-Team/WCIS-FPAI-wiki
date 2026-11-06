#!/usr/bin/env python3
"""Assemble the Quartz content folder from the WCIS doc library.

This script lives in the document repository, so the vault is its own repository
root: every Markdown page and media file under the tree is content, and the site
follows a page commit with no intermediate copy step.

Wikilinks resolve by file name across the whole vault, so pages are copied as a
set and cross-folder links keep working. Only Markdown plus the media types pages
actually embed are copied; build outputs, models and vendor archives stay out.

Directories listed in RAW_DIRS and files matching RAW_FILES hold converted vendor
material (datasheet dumps, scraped blogs, board forensics, DOCX conversions).
Their pages are not published unless --all is given, but media they hold that a
published page embeds is still copied -- otherwise those pages come out with
broken images. A page that becomes raw while other pages still link to it leaves
a dead link on the site: page targets are NOT audited here, only media embeds and
duplicate names are. That is why one oversized converted file goes in through
RAW_FILES instead of its whole folder.

Usage:
  python -X utf8 site/make-content.py                  curated set -> site/content
  python -X utf8 site/make-content.py --all            also the vendor dumps
  python -X utf8 site/make-content.py --dest D         write somewhere else (CI)
  python -X utf8 site/make-content.py --audit-only     report, write nothing

Exit status is 0 when every embedded media file resolves.
"""

import argparse
import fnmatch
import os
import re
import shutil
import subprocess
import sys
from urllib.parse import unquote

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TREES = ("",)
HOME_PAGE = "README.md"
HOME_TARGET = "index.md"

RAW_DIRS = {
    "modellist",
    "modrt",
    "modtest",
    "psrt",
    "fpai-blog",
    "repo2WCIS.repos",
    "board_extract",
    # image folder shipped with the FAQ DOCX dump below; keeping it raw means the
    # dump's pictures do not ride along as orphans once the dump is unpublished.
    "FAQ共建_images",
}
# File-name patterns treated as raw material even when the page sits in an
# authored folder. This is the knob for "one big converted file inside man/",
# because putting its whole directory in RAW_DIRS would also drop the authored
# pages next to it - and those are linked by other published pages, so the site
# would keep linking to pages it no longer contains.
RAW_FILES = ("*.docx.md",)
# Pages that are never published, --all included. This is the site-side copy of a
# note that stays a local tool: the vault-rooted conventions page carries agent
# instructions and host logins, and nothing links to it by name, so leaving it out
# costs no dead link.
NEVER_PUBLISH = ("agent.md",)
SKIP_DIRS = {".obsidian", ".git", ".vscode", "node_modules", ".quartz-cache",
             "site", "qbuild", "public", "__pycache__",
             # 第三方资料集中区：厂商正文/转载/抓取件，连媒体也不进站点。
             # 与 .gitignore 的 /official/* 对齐；git_visible() 是第二道闸。
             "official"}
MEDIA_EXT = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
    ".bmp",
    ".ico",
    ".mp4",
    ".webm",
}
SENTINEL = ".generated-by-make-content"

WIKILINK = re.compile(r"(!?)\[\[([^\[\]]+?)\]\]")
MDLINK = re.compile(r"(!?)\[([^\]]*)\]\(([^()\s]+)(?:\s+\"[^\"]*\")?\)")


def rel(path):
    return os.path.relpath(path, REPO).replace(os.sep, "/")


def is_raw(relpath):
    parts = relpath.split("/")
    return any(p in RAW_DIRS for p in parts) or any(
        fnmatch.fnmatch(parts[-1], pat) for pat in RAW_FILES)


def is_never_published(relpath):
    return os.path.basename(relpath) in NEVER_PUBLISH


def git_visible():
    """Repo-relative paths git would publish: tracked + untracked, minus ignored.

    This makes the site obey .gitignore instead of a second hand-kept list:
    official/ (vendor dumps), board_extract/ forensics and every size rule are
    excluded exactly as they are from the repository. Returns None when git is
    unavailable, in which case SKIP_DIRS still keeps the big vendor folder out.
    """
    try:
        out = subprocess.run(
            ["git", "-C", REPO, "ls-files", "-z", "--cached", "--others",
             "--exclude-standard"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True).stdout
    except Exception:
        return None
    return {p.decode("utf-8", "replace") for p in out.split(b"\0") if p}


def walk_vault():
    """All Markdown and media under the doc trees, as repo-relative paths."""
    visible = git_visible()
    md, media = [], []
    for tree in TREES:
        root = os.path.join(REPO, tree)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
            if any(p in SKIP_DIRS for p in dirpath.replace(os.sep, "/").split("/")):
                continue
            for name in sorted(filenames):
                ext = os.path.splitext(name)[1].lower()
                path = rel(os.path.join(dirpath, name))
                if visible is not None and path not in visible:
                    continue
                if ext == ".md":
                    md.append(path)
                elif ext in MEDIA_EXT:
                    media.append(path)
    return md, media


def target_name(relpath):
    return HOME_TARGET if relpath == HOME_PAGE else relpath


def split_wikilink(body):
    return body.split("|", 1)[0].split("#", 1)[0].strip()


def refs(text):
    """Yield (is_media_hint, target) for every local reference in a page."""
    for m in WIKILINK.finditer(text):
        yield False, split_wikilink(m.group(2))
    for m in MDLINK.finditer(text):
        target = unquote(m.group(3).strip()).replace("\\", "/")
        if re.match(r"^[a-z]+:", target, re.I) or target.startswith("//"):
            continue
        yield os.path.splitext(target)[1].lower() in MEDIA_EXT, target


def media_indexes(media):
    """(path lookup, basename lookup) the way Obsidian resolves a link."""
    by_name = {}
    by_path = {}
    for m in media:
        by_name.setdefault(os.path.basename(m).casefold(), []).append(m)
        by_path[m.lower()] = m
    return by_path, by_name


def resolve(target, source, media_index, media_names):
    """Find the vault path an embedded target points at, Obsidian-style."""
    if not target:
        return None
    base = os.path.basename(target).casefold()
    if "/" in target:
        guess = os.path.normpath("/".join(p for p in (os.path.dirname(source), target) if p))
        if guess.replace("\\", "/").lower() in media_index:
            return media_index[guess.replace("\\", "/").lower()]
    hits = media_names.get(base)
    if hits:
        return hits[0]
    return None


def rewrite_media(text, source, media_index, media_names):
    """Spell out the full vault path in every media embed.

    Obsidian resolves a bare file name anywhere in the vault, Quartz joins the
    link with the page's own folder instead (its basename matching only covers
    pages, not assets), so ![[foo.png]] in wiki/A/B.md looks for
    wiki/A/foo.png. The asset emitter copies to the content-relative path, so
    writing that path here is what makes the emitted src hit the file. Only the
    generated copy changes -- the notes keep Obsidian's shortest-link form.
    """
    count = 0
    edits = []

    for m in WIKILINK.finditer(text):
        if m.group(1) != "!":
            continue
        link = m.group(2).split("|", 1)[0]
        raw_name = link.split("#", 1)[0]
        hit = resolve(raw_name.strip(), source, media_index, media_names)
        if not hit or hit == raw_name.strip():
            continue
        start = m.start(2)
        edits.append((start, start + len(raw_name), hit))

    for m in MDLINK.finditer(text):
        if m.group(1) != "!":
            continue
        raw = m.group(3).strip()
        target = unquote(raw).replace("\\", "/")
        if re.match(r"^[a-z]+:", target, re.I) or target.startswith("//"):
            continue
        hit = resolve(target, source, media_index, media_names)
        if not hit or hit == target:
            continue
        edits.append((m.start(3), m.end(3), hit.replace(" ", "%20")))

    for start, end, new in sorted(edits, reverse=True):
        text = text[:start] + new + text[end:]
        count += 1
    return text, count


def select(pages, media, include_raw):
    """Pick the content set: pages plus the media they embed."""
    by_path, by_name = media_indexes(media)

    pages = [p for p in pages if not is_never_published(p)]
    chosen_pages = [p for p in pages if include_raw or not is_raw(p)]
    chosen_media = set()
    unresolved = []
    if include_raw:
        chosen_media.update(media)
    else:
        chosen_media.update(m for m in media if not is_raw(m))
        for p in chosen_pages:
            text = open(os.path.join(REPO, p.replace("/", os.sep)), encoding="utf-8", errors="replace").read()
            for is_media, target in refs(text):
                if not is_media:
                    continue
                hit = resolve(target, p, by_path, by_name)
                if hit:
                    chosen_media.add(hit)
                else:
                    unresolved.append((p, target))
    chosen_media = sorted(c for c in chosen_media if os.path.isfile(os.path.join(REPO, c.replace("/", os.sep))))
    return chosen_pages, chosen_media, unresolved


def check_unique_names(chosen_pages):
    """shortest-link resolution needs unique page file names."""
    seen = {}
    dupes = {}
    for p in chosen_pages:
        key = os.path.basename(p).casefold()
        seen.setdefault(key, []).append(p)
    for key, paths in seen.items():
        if len(paths) > 1:
            dupes[key] = paths
    return dupes


def rename_lookup():
    """Old repo path -> the path it holds now, for moves already committed.

    The date walk runs with --no-renames, so each commit prints the path it
    actually held. Without this map a tree that was folded into another one
    stops matching any page on its old side and reports the move commit as its
    creation date. Scanned over the whole history, not just the current pages,
    because the old side of a move is usually outside them.
    """
    cmd = ["git", "-c", "core.quotePath=false", "-C", REPO, "log", "--format=%H",
           "--name-status", "--diff-filter=R"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", check=True).stdout
    except Exception:
        return {}
    direct = {}
    for line in out.splitlines():
        parts = line.strip().split("\t")
        if len(parts) == 3 and parts[0].startswith("R"):
            direct.setdefault(parts[1].replace("\\", "/"), parts[2].replace("\\", "/"))
    resolved = {}
    for old in direct:
        cur, hops = old, 0
        while cur in direct and hops < len(direct):
            cur = direct[cur]
            hops += 1
        if cur != old:
            resolved[old] = cur
    return resolved


def git_dates(paths):
    """repo path -> (first commit day, last commit day).

    The date plugin reads frontmatter before git, and the generated content
    folder is not tracked in any repo -- without this every page would show the
    build date. One log walk, newest first, so the oldest day seen last is the
    creation date. This repository carries the pages' whole past: the history
    came across with the subtree split, so no second repository is read.
    """
    moved = rename_lookup()
    # No pathspec here on purpose: a move commit prints the old path on its own
    # line, and limiting the walk to the current pages would drop every day the
    # page spent under its former name.
    cmd = ["git", "-c", "core.quotePath=false", "-C", REPO, "log", "--format=%cs", "--name-only",
           "--no-renames"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", check=True).stdout
    except Exception as exc:
        print(f"git history unreadable, pages keep no dates: {exc}", file=sys.stderr)
        return {}
    seen = {}
    day = None
    for line in out.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            day = s
            continue
        p = s.replace("\\", "/")
        p = moved.get(p, p)
        if p not in paths or day is None:
            continue
        cur = seen.get(p)
        if cur is None:
            seen[p] = [day, day]
        else:
            cur[0] = min(cur[0], day)
            cur[1] = max(cur[1], day)
    return {p: (v[0], v[1]) for p, v in seen.items()}


def inject_dates(text, created, modified):
    """Add created/modified to a page's frontmatter without touching existing keys."""
    want = {"created": created, "modified": modified}
    lines = text.split("\n")
    close = None
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                close = i
                break
        else:
            return text
    have = set()
    for i in range(1, close if close is not None else 0):
        m = re.match(r"([A-Za-z_][\w-]*)\s*:", lines[i])
        if m:
            have.add(m.group(1))
    add = [f"{k}: {v}" for k, v in want.items() if k not in have]
    if not add:
        return text
    if close is None:
        return "---\n" + "\n".join(add) + "\n---\n" + text
    lines[close:close] = add
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dest", default=os.path.join(REPO, "site", "content"))
    ap.add_argument("--all", action="store_true", help="include vendor dump dirs")
    ap.add_argument("--audit-only", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 1 on unresolved embeds or duplicate names")
    args = ap.parse_args(argv)

    dest_root = os.path.abspath(args.dest)
    if os.path.basename(dest_root).replace("\\", "/") not in ("content", "content-test"):
        print(f"refusing to write {dest_root}: destination must be named content/", file=sys.stderr)
        return 2

    pages, media = walk_vault()
    chosen_pages, chosen_media, unresolved = select(pages, media, args.all)
    total = len(chosen_pages) + len(chosen_media)
    size = sum(os.path.getsize(os.path.join(REPO, p.replace("/", os.sep))) for p in chosen_pages + chosen_media)
    print(f"selected {len(chosen_pages)} md + {len(chosen_media)} media = {size / 1048576:.1f} MB")
    if unresolved:
        print(f"embeds that point at no file on disk: {len(unresolved)}")
        for p, t in unresolved:
            print("  MISSING", p, "->", t)
    dupes = check_unique_names(chosen_pages)
    if dupes:
        print(f"duplicate page names, shortest links become ambiguous: {len(dupes)}")
        for key, paths in list(dupes.items())[:20]:
            print("  DUP", key, paths)

    if args.audit_only:
        return (1 if (unresolved or dupes) else 0) if args.strict else 0

    sentinel = os.path.join(dest_root, SENTINEL)
    if os.path.isdir(dest_root) and os.listdir(dest_root) and not os.path.exists(sentinel):
        print(f"refusing to wipe {dest_root}: no {SENTINEL} marker there", file=sys.stderr)
        return 2
    if os.path.isdir(dest_root):
        shutil.rmtree(dest_root)
    os.makedirs(dest_root, exist_ok=True)

    written = []
    dates = git_dates(set(chosen_pages))
    by_path, by_name = media_indexes(media)
    undated = 0
    rewritten = 0
    for p in chosen_pages + chosen_media:
        name = target_name(p)
        src = os.path.join(REPO, p.replace("/", os.sep))
        out = os.path.join(dest_root, name.replace("/", os.sep))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        text = None
        if p.endswith(".md"):
            try:
                with open(src, encoding="utf-8") as fh:
                    text = fh.read()
            except UnicodeDecodeError:
                text = None
            if text is not None:
                text, n = rewrite_media(text, p, by_path, by_name)
                rewritten += n
                if p in dates:
                    text = inject_dates(text, *dates[p])
                else:
                    undated += 1
        if text is None:
            shutil.copy2(src, out)
        else:
            with open(out, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
        written.append(name)

    with open(sentinel, "w", encoding="utf-8") as fh:
        fh.write("generated by site/make-content.py -- wiped on every build\n")
    print(f"wrote {len(written)} files -> {dest_root}")
    print(f"pages with commit dates in frontmatter: {len(chosen_pages) - undated}, undated: {undated}")
    print(f"media embeds rewritten to their full path: {rewritten}")
    return (1 if (unresolved or dupes) else 0) if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
