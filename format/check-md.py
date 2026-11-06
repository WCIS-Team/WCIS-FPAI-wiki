import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
# Roots named on the command line must exist: a typo there is a hard error.
# The default roots are the trees that actually exist, so a vault that has been
# renamed or merged away does not abort a full-library check.
EXPLICIT = [os.path.abspath(a) for a in sys.argv[1:]]
DEFAULT_ROOTS = [os.path.join(REPO, "wiki"), os.path.join(REPO, "archive")]
VAULTS = EXPLICIT if EXPLICIT else [v for v in DEFAULT_ROOTS if os.path.isdir(v)]
# directories whose .md are imported raw material (vendor model-zoo docs,
# scraped blog posts, forensic extractions, the old GitHub wiki dump): not
# authored pages, so the page-shape and body checks do not apply to them.
# Their names still resolve wikilinks pointing at them. Edit this list when a
# dump tree lands in the vault - each entry matches at any depth.
# "man" is exempted wholesale on 2026-10-18 at her request: it holds the 224k
# token FAQ DOCX dump, and the rest of the folder is reference notes rather than
# pages that should carry the authored-page shape. Its pages still ship on the
# site - site/make-content.py drops only the dump itself, by RAW_FILES.
RAW_DIRS = {"modellist", "modrt", "modtest", "psrt", "fpai-blog",
            "repo2WCIS.repos", "board_extract", "man",
            # "schoolhardware" is the校机 (Windows host) SOP 2 archive: machine
            # output (JSON + raw_logs + generated md), added 2026-10-20. It keeps
            # two files named sources.md (live + archive-v1.0 snapshot), so
            # without this entry the duplicate-page-name rule fires on them.
            "schoolhardware",
            # "Procise手册Markdown" is the vendor Procise manual set converted to
            # Markdown (16 files), landed 2026-10-31 with the FPGArt tree: same
            # shape as the other dumps - H1s are the manual titles, no
            # related-pages section, and the <>-looking tokens are register names.
            "Procise手册Markdown",
            # "4compile" is the bitstream build workspace, untracked by her ruling
            # on 2026-10-31 (.gitignore names it). It stays on disk, so the walk
            # still reaches its vendor notes; exempting it keeps the count honest.
            "4compile"}

# pages whose H1 is a descriptive title instead of the file name
# (Home.md was the old front page; the reorg replaced it with wiki/README.md)
H1_EXEMPT = {"Home", "README"}

# top-level folders holding raw working notes: they are records, not wiki pages,
# so the page-shape rules (H1) do not apply to them.
# "agentpreview" holds the drafts of the main-repo root docs (AGENTS／ARCHITECTURE／
# CONTRIBUTING／llms) staged for review, added 2026-10-31: their H1 is the document
# title by design, so they are not pages - but they still ship nothing to the site.
APPENDIX_DIRS = {"1111操作记录", "agentpreview"}

# site/make-content.py writes page copies inside the vault (wiki/site/content*/);
# scanning them would double every problem and hand progress.py two ledger pages.
BUILD_DIRS = {"site", "qbuild", "public", "node_modules", ".quartz-cache"}

TAG = re.compile(r"<[a-zA-Z][a-zA-Z0-9_.-]*(\s[^<>]*)?>")
FENCE = re.compile(r"^\s{0,3}(```|~~~)")
# A leading YAML block is metadata, not prose (`tags: [SOP]`, `updated: ...`).
# It must not be scanned for links or HTML-looking tags, and it must not push
# the H1 off the first line, so every content check runs on the body after it.
FRONTMATTER = re.compile(r"\A\ufeff?---\r?\n.*?\r?\n---\r?\n", re.DOTALL)
# the blank line that usually sits between the frontmatter and the H1
BLANK_LINE = re.compile(r"^[ \t]*\r?\n")
WIKI = re.compile(r"\[\[([^\]\[]*)\]\]")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")
BLOCK_ID = re.compile(r"\s\^([A-Za-z0-9-]+)\s*$")
INLINE_CODE = re.compile(r"`[^`]*`")
NODE_LABEL = re.compile(r"([A-Za-z_][\w-]*)\s*[\[\{]\s*\"([^\"]*)\"")
CLASS_STMT = re.compile(r"^\s*class\s+([A-Za-z0-9_,\-\s]+)\s+([A-Za-z0-9_\-]+)\s*$")
# `## 相关页面` is no longer required (D-1793628864, 2026-11-02): she weighed
# deleting every such footer, and the measurement said the section is a real
# navigation aid (749 of 2928 wikilinks live there, 267 of them appear nowhere
# else, and 10 hub pages take 17-44% of their in-links from footers) but the
# "every page must have one" rule only ever produced 38 findings on pages that
# simply do not need one. So the rule is gone and the sections stay where an
# author wrote them. RELATED is kept as a name other tooling may grep for.
RELATED = "## 相关页面"


def split_frontmatter(text):
    """(body, first_line): drop a leading YAML block, then the blank line that
    usually separates it from the H1. first_line is 1-based and stays relative
    to the file, so reported numbers point at the real lines."""
    match = FRONTMATTER.match(text)
    if not match:
        return text, 1
    body = text[match.end():]
    while True:
        blank = BLANK_LINE.match(body)
        if not blank:
            break
        body = body[blank.end():]
    consumed = len(text) - len(body)
    return body, text[:consumed].count("\n") + 1


def walk(root):
    """(checked, indexed). Raw-material trees still provide link targets,
    they are only exempt from the page-shape and body checks."""
    checked, indexed = [], []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in BUILD_DIRS]
        dirnames.sort()
        here = os.path.relpath(dirpath, root)
        raw = here != "." and any(part in RAW_DIRS for part in here.split(os.sep))
        for name in sorted(filenames):
            if not name.endswith(".md"):
                continue
            path = os.path.join(dirpath, name)
            indexed.append(path)
            if not raw:
                checked.append(path)
    return sorted(checked), sorted(indexed)


def mermaid_links(path, text, names, line0=1):
    problems = []
    in_block = False
    labels = {}
    for num, raw in enumerate(text.split("\n"), line0):
        if FENCE.match(raw):
            lang = raw.strip().lstrip("`~").lower()
            if not in_block and lang.startswith("mermaid"):
                in_block = True
                labels = {}
            elif in_block:
                in_block = False
            continue
        if not in_block:
            continue
        for match in NODE_LABEL.finditer(raw):
            labels[match.group(1)] = match.group(2)
        match = CLASS_STMT.match(raw)
        if match and match.group(2) == "internal-link":
            for node in match.group(1).split(","):
                node = node.strip()
                if not node:
                    continue
                label = labels.get(node)
                if label is None:
                    problems.append((path, num, "internal-link node " + node + " has no quoted label"))
                elif label not in names:
                    problems.append((path, num, "internal-link node label [" + label + "] is not a page name"))
    return problems


def headings_and_blocks(text):
    """Every heading title and block id in a page - what a #anchor can point at.
    YAML frontmatter is dropped: it is metadata, and a `# comment` in it is not a
    heading, so it must not become a resolvable anchor."""
    text = split_frontmatter(text)[0]
    heads, blocks = set(), set()
    in_fence = False
    for raw in text.split("\n"):
        if FENCE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", raw)
        if match:
            title = match.group(1).strip()
            heads.add(title)
            heads.add(" ".join(title.split()))
            continue
        match = re.search(r"\s\^([A-Za-z0-9-]+)\s*$", raw)
        if match:
            blocks.add(match.group(1))
    return heads, blocks


def is_raw(path):
    for vault in VAULTS:
        if path.startswith(vault + os.sep):
            here = os.path.relpath(os.path.dirname(path), vault)
            return any(part in RAW_DIRS for part in here.split(os.sep))
    return False


def display(path):
    for vault in VAULTS:
        if path.startswith(vault + os.sep):
            return os.path.relpath(path, vault).replace(os.sep, "/")
    return path.replace(os.sep, "/")


def main():
    files, indexed = [], []
    if not VAULTS:
        print("no vault directory exists")
        return 2
    for vault in VAULTS:
        if not os.path.isdir(vault):
            print("not a directory: " + vault)
            return 2
        checked, all_files = walk(vault)
        files += checked
        indexed += all_files
    files.sort()
    names = {}
    anchors = {}
    for path in indexed:
        base = os.path.basename(path)[:-3]
        names.setdefault(base, []).append(path)
        heads, blocks = headings_and_blocks(io.open(path, encoding="utf-8").read())
        anchors.setdefault(base, (heads, blocks))

    problems = []
    for base, paths in sorted(names.items()):
        if len(paths) > 1 and not all(is_raw(p) for p in paths):
            for path in paths:
                problems.append((path, 0, "duplicated page name (wikilinks become ambiguous)"))

    for path in files:
        blob = io.open(path, encoding="utf-8").read()
        title = os.path.basename(path)[:-3]
        rel = display(path)
        is_appendix = rel.split("/", 1)[0] in APPENDIX_DIRS
        if blob.startswith("\ufeff"):
            problems.append((path, 0, "BOM at file start"))
        if "\r\n" in blob:
            problems.append((path, 0, "CRLF line endings"))

        # shape and body checks run on the body: frontmatter is metadata
        text, line0 = split_frontmatter(blob)

        in_fence = False
        for num, raw in enumerate(text.split("\n"), line0):
            if FENCE.match(raw):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            line = INLINE_CODE.sub("", raw)
            for match in TAG.finditer(line):
                problems.append((path, num, "bare HTML-looking placeholder " + match.group(0)))
            for match in WIKI.finditer(line):
                inner = match.group(1).split("|")[0].strip().rstrip("\\")
                page, _, frag = inner.partition("#")
                page = page.strip()
                if page not in names:
                    problems.append((path, num, "unresolved wikilink [[" + page + "]]"))
                    continue
                if not frag:
                    continue
                heads, blocks = anchors[page]
                frag = frag.strip()
                if frag.startswith("^"):
                    if frag[1:] not in blocks:
                        problems.append((path, num, "missing block ^" + frag[1:]
                                         + " in [[" + page + "]]"))
                elif frag not in heads and " ".join(frag.split()) not in heads:
                    problems.append((path, num, "missing section #" + frag
                                     + " in [[" + page + "]]"))

        # No "missing related-pages section" check: the section is optional as of
        # D-1793628864 (2026-11-02). Its links still feed the graph and the
        # backlinks, so keep writing it where it helps a reader; it is not a
        # page-shape requirement any more.
        first = text.split("\n", 1)[0]
        if not first.startswith("# ") and title not in H1_EXEMPT and not is_appendix:
            problems.append((path, 0, "first line is not an H1"))
        elif (first.startswith("# ") and title not in H1_EXEMPT and not is_appendix
                and first[2:].strip() != title):
            problems.append((path, 0, "H1 does not match file name"))

        problems.extend(mermaid_links(path, text, names, line0))

    counts = {}
    for path, num, message in problems:
        counts.setdefault((path, message), []).append(num)

    if not counts:
        print("OK: " + str(len(files)) + " pages, no issues")
        return 0

    for (path, message), nums in sorted(counts.items()):
        where = "" if nums == [0] else ":" + ",".join(str(n) for n in nums[:6])
        print(display(path) + where + "  " + message)
    print("---")
    print(str(len(problems)) + " problems in " + str(len(counts)) + " groups")
    return 1


if __name__ == "__main__":
    sys.exit(main())
