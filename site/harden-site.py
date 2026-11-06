"""Post-build trimming and crawler hardening for the Quartz site.

Runs after `quartz build` and before the Pages artifact is uploaded:

  * writes robots.txt (deny-all, from site/robots.txt next to this script)
  * deletes the generated sitemap and the RSS feed, both indexes handed to crawlers
  * puts a noindex meta tag in the head of every generated page
  * strips each page's body text out of static/contentIndex.json
  * adds the tags field to the search query so titles and tags both recall
  * prefixes the client bundle's root-absolute paths with the site's own root
  * moves the stylesheet every page duplicates into one cached file

GitHub Pages serves static files and gives no way to set X-Robots-Tag, so the
document-level tag is the only signal a crawler that already has the URL sees.
Both are requests, not enforcement: anything that ignores them still gets the
bytes. That is why this step exists in the pipeline rather than as a one-off.
"""

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import sys

META = '<meta name="robots" content="noindex, nofollow, noimageindex, noai, noimageai"/>'
# Quartz v5.0.0 writes the RSS feed (enableRSS: true) to index.xml, not to feed.xml or
# rss.xml - so the two names D-67 listed here were the sitemap only and the feed, a
# list of the last ten page URLs, stayed published. Nothing links it, so deleting it
# costs a reader nothing it could reach; no page head carries an alternate link.
CRAWLER_INDEXES = ("sitemap.xml", "sitemap-0.xml", "feed.xml", "rss.xml", "index.xml")
HEAD_RE = re.compile(r"(<head[^>]*?>)", re.IGNORECASE)
# Rename only the graph component heading, leaving article text untouched.
GRAPH_TITLE_RE = re.compile(
    r'(<div\b[^>]*\bclass="(?:[^"]*\s)?graph(?:\s[^"]*)?"[^>]*>\s*<h3>)Graph View(</h3>)'
)
CONTENT_INDEX = pathlib.PurePosixPath("static", "contentIndex.json")
BASE_URL_RE = re.compile(r"^\s*baseUrl:\s*(\S+)\s*$", re.M)
BUNDLE = "postscript.js"
# The bundle assumes a site at the domain root: it fetches /static/contentIndex.json
# and links to "/" + slug. This site lives under /<repo>, so every one of those
# lands outside the site - sidebar tree, search, graph, popovers and result links
# all fail. Counted exactly so a Quartz upgrade that moves the code fails here
# instead of shipping a site whose interactive parts are dead.
ROOT_PATCHES = (
    ('fetch("/static/contentIndex.json")', 'fetch("{root}/static/contentIndex.json")', 3),
    ('new URL("/"+', 'new URL("{root}/"+', 1),
    ('href="/"+', 'href="{root}/"+', 3),
)
# The basic query names the fields FlexSearch should look in. Body text is gone
# from the index, so without this a query only ever matches titles and a page is
# unreachable by any of its tags. "content" stays listed - it is harmless empty
# and removing it would be a second edit of the same literal at every upgrade.
SEARCH_PATCHES = (
    ('index:["title","content"]', 'index:["title","content","tags"]', 1),
)
STYLE_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.S)
STYLE_DIR = pathlib.PurePosixPath("assets")
# data-persist is what the site's own external stylesheets carry. The bundle clears
# `document.head:not([data-persist])` on every in-site navigation and re-adds the
# fetched document's head nodes, so an unpersisted link is removed and re-added on
# each click - and a link that has to load again (even from cache) leaves the page
# unstyled for that beat. Persisted, the one file stays put for the whole session.
STYLE_LINK = '<link href="{root}/{dir}/site-{digest}.css" rel="stylesheet" type="text/css" data-persist="true"/>'
# Detecting an already-externalised tree means matching the whole tag this step emits,
# not a path prefix. Pages quote `/assets/site-...` in prose all the time - the SOP's
# own curl recipes do - and inside `<code>` only quotes and angle brackets get escaped,
# so a bare `/assets/site-` survives into the rendered HTML verbatim. Anchored on the
# literal `<link href="`, a code sample cannot collide: `<` always renders as `&lt;`.
STYLE_LINK_RE = re.compile(
    r'<link href="[^"]*/assets/site-([0-9a-f]{12})\.css" rel="stylesheet" type="text/css" data-persist="true"/>'
)


def write(path, text):
    """Write bytes as-is - write_text's default translates LF to CRLF on Windows.

    The pipeline runs on Linux so CI never sees it, but a verification run on this
    machine rewrites every page's endings and inflates the sizes it reports.
    """
    path.write_text(text, encoding="utf-8", newline="")


def shared_style(public, root, pages):
    """Move the stylesheet every page carries into one cached file.

    Quartz inlines its whole theme into a `<style>` block in the head of each page -
    417,916 B of the 473,308 B home document, byte-identical on all 124 pages. An
    inline block has no URL, so it is not cacheable: the browser pays for it on each
    page load and, because navigation here fetches whole documents, on each in-site
    click too. The link is left exactly where the block was so the `@layer` order
    statement and the preceding stylesheet links keep their relative position, and
    named by the digest of its bytes so a theme change busts the cache by itself.

    Fails if the largest block is not the same bytes on every page or if the tree is
    half-patched - a Quartz upgrade that starts emitting per-page styles must stop the
    build rather than publish pages styled by another page's CSS.
    """
    links = 0
    for page in pages:
        if STYLE_LINK_RE.search(page.read_text(encoding="utf-8")):
            links += 1
    if links == len(pages):
        names = set()
        for page in pages:
            match = STYLE_LINK_RE.search(page.read_text(encoding="utf-8"))
            names.add(match.group(1))
        if len(names) != 1:
            sys.exit("pages point at %d different stylesheets - the tree is inconsistent" % len(names))
        path = public / pathlib.Path(STYLE_DIR) / ("site-%s.css" % names.pop())
        if not path.is_file():
            sys.exit("%s is linked by every page but is missing" % path)
        return path.stat().st_size, "already externalised"
    if links:
        sys.exit("%d of %d pages already link an externalised stylesheet - mixed state" % (links, len(pages)))

    biggest = {}
    for page in pages:
        text = page.read_text(encoding="utf-8")
        end = text.find("</head>")
        blocks = [m for m in STYLE_RE.finditer(text) if end < 0 or m.start() < end]
        if not blocks:
            sys.exit("%s has no <style> block in its head" % page)
        block = max(blocks, key=lambda m: len(m.group(1).encode("utf-8")))
        css = block.group(1)
        digest = hashlib.sha256(css.encode("utf-8")).hexdigest()[:12]
        biggest.setdefault(digest, []).append((page, text, block.span(), css))
    if len(biggest) != 1:
        sys.exit("the largest <style> block differs across pages (%d distinct) - refusing to share one stylesheet" % len(biggest))
    digest, hits = next(iter(biggest.items()))
    css = hits[0][3]
    out_dir = public / pathlib.Path(STYLE_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    write(out_dir / ("site-%s.css" % digest), css)
    tag = STYLE_LINK.format(root=root.rstrip("/"), dir=str(STYLE_DIR), digest=digest)
    for page, text, (start, stop), _ in hits:
        write(page, text[:start] + tag + text[stop:])
    return len(css.encode("utf-8")), "%d pages" % len(hits)


def site_root(config_path):
    """Path part of configuration.baseUrl - empty for a domain-root site."""
    match = BASE_URL_RE.search(config_path.read_text(encoding="utf-8"))
    if not match:
        sys.exit("no baseUrl: line in %s - cannot work out the site root" % config_path)
    base = match.group(1)
    return "/" + base.split("/", 1)[1].strip("/") if "/" in base else ""


def patch_bundle(public, root):
    path = public / BUNDLE
    if not path.is_file():
        sys.exit("no %s under %s - refusing to publish a site with root-absolute paths" % (BUNDLE, public))
    text = path.read_text(encoding="utf-8")
    for old, new, expected in ROOT_PATCHES + SEARCH_PATCHES:
        want = new.format(root=root)
        found = text.count(old)
        if found:
            if found != expected:
                sys.exit("%s: %d copies of %s, expected %d - the bundle changed" % (path, found, old, expected))
            text = text.replace(old, want)
        elif text.count(want) != expected:
            sys.exit("%s: neither %s nor its patched form is present %d times" % (path, old, expected))
    write(path, text)
    return root


def trim_index(public):
    """Drop the body text from every search index entry.

    The search client reads `fileData.content || ""`, so an absent body indexes
    as empty and only SEARCH_PATCHES' fields - title and tags - can match. slug,
    filePath, links and tags stay, so results still resolve and the graph,
    backlinks and tag pages are unaffected.
    Missing or reshaped index means upstream changed it - fail rather than publish
    the full bodies unnoticed.
    """
    path = public / pathlib.Path(CONTENT_INDEX)
    if not path.is_file():
        sys.exit("no %s under %s - refusing to publish an untrimmed index" % (CONTENT_INDEX, public))
    try:
        index = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        sys.exit("%s is not valid JSON: %s" % (path, exc))
    if not isinstance(index, dict):
        sys.exit("%s is a %s, expected an object keyed by slug" % (path, type(index).__name__))

    before = path.stat().st_size
    stripped = 0
    for entry in index.values():
        if isinstance(entry, dict) and entry.pop("content", None) is not None:
            stripped += 1
    if not stripped:
        sys.exit("%s carries no body field - the index shape changed" % path)
    write(path, json.dumps(index, ensure_ascii=False, separators=(",", ":")))
    return before, path.stat().st_size, stripped


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("public", help="directory holding the built site")
    args = ap.parse_args()

    public = pathlib.Path(args.public)
    pages = sorted(public.rglob("*.html"))
    if not pages:
        sys.exit("no HTML under %s - refusing to publish an unhardened site" % public)

    injected = 0
    already = 0
    graph_labels = 0
    for page in pages:
        text = page.read_text(encoding="utf-8")
        text, labels = GRAPH_TITLE_RE.subn(r"\1Graph View (Ctrl+G)\2", text)
        if labels:
            write(page, text)
            graph_labels += labels
        if 'name="robots"' in text:
            already += 1
            continue
        new, hits = HEAD_RE.subn(lambda m: m.group(1) + META, text, count=1)
        if hits == 0:
            sys.exit("%s has no <head> tag to inject into" % page)
        write(page, new)
        injected += 1

    if not graph_labels:
        sys.exit("no Graph View headings found - refusing to publish without the shortcut label")
    print("Graph View shortcut labels: %d" % graph_labels)

    robots_src = pathlib.Path(__file__).resolve().parent / "robots.txt"
    shutil.copyfile(robots_src, public / "robots.txt")

    removed = [name for name in CRAWLER_INDEXES if (public / name).exists()]
    for name in removed:
        (public / name).unlink()

    idx_before, idx_after, stripped = trim_index(public)
    root = patch_bundle(public, site_root(pathlib.Path(__file__).resolve().parent / "quartz.config.yaml"))
    css_bytes, css_note = shared_style(public, root, pages)
    print(
        "hardened %d pages (%d already carried a robots tag), wrote robots.txt, "
        "removed %s, trimmed %s from %d to %d bytes (%d bodies dropped), "
        "re-rooted the bundle on %s, made the search query take title+tags, "
        "moved the shared stylesheet (%d bytes, %s) out of every page's head"
        % (injected + already, already, removed or ["nothing"], CONTENT_INDEX,
           idx_before, idx_after, stripped, root or "the domain root",
           css_bytes, css_note)
    )


if __name__ == "__main__":
    main()
