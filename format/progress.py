#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Derive the board summary from the task-card ledger.

The board page holds one ledger table: a row per task card. That table is the
only progress source of truth. This script reads it, checks the bookkeeping
rules and regenerates the summary block, so the printed percentages can never
drift from the rows they come from.

Regions are located by HTML-comment markers, which Obsidian renders as nothing:

    <!-- ledger:begin --> ... <!-- ledger:end -->      read only
    <!-- blockers:begin --> ... <!-- blockers:end -->  read only
    <!-- progress:begin --> ... <!-- progress:end -->  written by this script
    <!-- checklist:begin --> ... <!-- checklist:end --> written by this script

The linear checklist on the checklist page is generated from the same ledger, so
a card is never ticked in one place and left open in another. Its detail page
comes from the ledger's last column, which is what makes the list, the flow
diagram and the detailed page point at the same document.

Usage:
  python -X utf8 wiki/format/progress.py            rewrite the summary block
  python -X utf8 wiki/format/progress.py --check    verify only, exit 1 on drift
  python -X utf8 wiki/format/progress.py --list     list the cards that are not done
  python -X utf8 wiki/format/progress.py --tick CARD STATUS [EVIDENCE]

Ticking happens in the ledger, never in the generated list: --tick A3 done
"E3 sim/run.log" rewrites that row's status, evidence and date in one step.
"""

import io
import os
import re
import sys
from datetime import date

# One tree since the archive/ fold-in (decision D-60): wiki/ holds the pages and
# wiki/archive/ holds the status source, the ledgers and the board.
DOC_DIRS = ("wiki",)

# site/make-content.py writes page copies inside the vault (wiki/site/content*/);
# a copy carries the same markers, so scanning it yields a second ledger page.
BUILD_DIRS = {"site", "qbuild", "public", "node_modules", ".quartz-cache"}

LEDGER_B, LEDGER_E = "<!-- ledger:begin -->", "<!-- ledger:end -->"
BLOCK_B, BLOCK_E = "<!-- blockers:begin -->", "<!-- blockers:end -->"
PROGRESS_B, PROGRESS_E = "<!-- progress:begin -->", "<!-- progress:end -->"
CHECK_B, CHECK_E = "<!-- checklist:begin -->", "<!-- checklist:end -->"

# One column per position, so the file stays readable without header lookup.
COL_CARD, COL_NAME, COL_GROUP, COL_ROUTE = 0, 1, 2, 3
COL_OWNER, COL_BACKUP, COL_EST, COL_ACTUAL = 4, 5, 6, 7
COL_STATUS, COL_EVIDENCE, COL_UPDATED, COL_NOBOARD, COL_NOTE = 8, 9, 10, 11, 12
COL_PAGE = 13
NCOL = 14

# Status symbols are shared with the board page.
S_TODO, S_DOING, S_BLOCKED, S_DONE, S_NA = "\u2b1c", "\U0001f504", "\u26d4", "\u2705", "\u2796"
STATUS = {S_TODO: "todo", S_DOING: "doing", S_BLOCKED: "blocked", S_DONE: "done", S_NA: "n/a"}

# Chinese labels written into the Markdown output. Escaped so this file stays
# ASCII-only, per the repo rule on script contents.
L_GROUP = "\u5206\u7ec4"
L_PLAN = "\u8ba1\u5212\u5361"
L_RATE = "\u5b8c\u6210\u7387"
L_TOTAL = "\u5408\u8ba1"
L_PROGRESS = "\u603b\u8fdb\u5ea6"
L_LATEST = "\u6700\u8fd1\u5237\u65b0"
L_EXCLUDED = "\u5254\u9664"
SEP = "\u3000"
DASHES = ("\u2014", "-", "")
DECISION = "D-"
NB_YES, NB_PART, NB_NO = "\u662f", "\u90e8\u5206", "\u5426"  # no-board split: yes / partial / no
# The four card groups, in the order the summary table prints them.
GROUPS = ("\u51c6\u5907", "\u57fa\u7ebf", "\u52a0\u901f", "\u4ea4\u4ed8")

# Checklist rendering. Chinese kept escaped so this file stays ASCII-only.
L_PHASE = "\u671f"                    # phase suffix on the group heading
L_ARROW = "\u2192"                    # card -> detail page
L_NOBOARD = "\u65e0\u677f"                # no board needed
L_WARN = "\u26a0 \u65e0\u5bf9\u5e94\u9875\u9762"
MID = " \u00b7 "
STATUS_ALIAS = {v: k for k, v in STATUS.items()}

CARD_ID = re.compile(r"^[A-Z]+[0-9]*$")
EVIDENCE = re.compile(r"^E[0-6]\s+\S")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ROUTE_RE = re.compile(r"^[\u2460\u2461\u2462\u2463]$")
RANGE = re.compile(r"([A-Z]+)(\d+)\s*[\u2013\u2014~-]\s*(?:([A-Z]+)\s*)?(\d+)")


CELL_SPLIT = re.compile(r"(?<!\\)\|")


def cells(line):
    # escaped pipes (\|) inside a cell are link aliases, not column separators
    return [c.strip() for c in CELL_SPLIT.split(line.strip().strip("|"))]


def table_rows(lines, lo, hi):
    """Data rows of the tables inside lines[lo:hi]; the first pipe row of a
    region is taken to be its header and skipped."""
    rows = []
    header_done = False
    for i in range(max(lo, 0), min(hi, len(lines))):
        line = lines[i]
        if not line.lstrip().startswith("|"):
            continue
        row = cells(line)
        if not row or set("".join(row)) <= set("-: "):
            continue
        if not header_done:
            header_done = True
            continue
        rows.append((i + 1, row))
    return rows


def marker_pair(lines, begin, end, path):
    try:
        b, e = lines.index(begin), lines.index(end)
    except ValueError:
        fail("%s: missing marker %s or %s" % (path, begin, end))
    if b > e:
        fail("%s: markers %s / %s are inverted" % (path, begin, end))
    for marker, side in ((begin, b + 1), (end, e - 1)):
        if lines[side].strip():
            fail("%s: %r must be followed/preceded by a blank line (file line %d), "
                 "otherwise Obsidian does not render the table"
                 % (path, marker, side + 1))
    return b, e


def rel(path, root):
    try:
        return os.path.relpath(path, root)
    except ValueError:  # different drive on Windows
        return path


def fail(msg):
    print(msg)
    sys.exit(1)


def read(path):
    with io.open(path, "r", encoding="utf-8", newline="") as fh:
        raw = fh.read()
    return raw.replace("\r\n", "\n"), ("\r\n" in raw)


def find_board(root):
    """The single Markdown page under the doc roots that carries the markers.

    A page qualifies only when the ledger pair and the progress pair are both
    present: quoting one marker string in prose must not pass for a board.
    """
    hits = [p for p in scan_md(root, PROGRESS_B) if is_board(p)]
    if len(hits) != 1:
        fail("expected exactly one page with %s, found %d: %s"
             % (PROGRESS_B, len(hits), ", ".join(hits) or "none"))
    return hits[0]


def has_markers(path, *markers):
    with io.open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    return all(m in text for m in markers)


def is_board(path):
    return has_markers(path, LEDGER_B, LEDGER_E, PROGRESS_B, PROGRESS_E)


def scan_md(root, marker):
    hits = []
    for doc in DOC_DIRS:
        for base, dirs, files in os.walk(os.path.join(root, doc)):
            dirs[:] = [d for d in dirs if d not in BUILD_DIRS]
            dirs.sort()
            for name in sorted(files):
                if not name.endswith(".md"):
                    continue
                path = os.path.join(base, name)
                with io.open(path, "r", encoding="utf-8") as fh:
                    if marker in fh.read():
                        hits.append(path)
    return hits


def render_checklist(cards):
    """The linear tick list, grouped and numbered in ledger order."""
    out = [CHECK_B, ""]
    for group in GROUPS:
        rows = [r for _, r in cards if r and r[COL_GROUP] == group]
        if not rows:
            continue
        done = sum(1 for r in rows if r[COL_STATUS] == S_DONE)
        plan = len([r for r in rows if r[COL_STATUS] != S_NA])
        out.append("### %s%s\uff08%d / %d\uff09" % (group, L_PHASE, done, plan))
        out.append("")
        for row in rows:
            box = "x" if row[COL_STATUS] == S_DONE else " "
            parts = ["- [%s] **%s** %s" % (box, row[COL_CARD], row[COL_NAME]),
                     row[COL_STATUS]]
            if row[COL_EVIDENCE] not in DASHES:
                parts.append(row[COL_EVIDENCE])
            parts.append("%s %s" % (L_ARROW, row[COL_PAGE] or L_WARN))
            if row[COL_NOBOARD] == NB_YES:
                parts.append(L_NOBOARD)
            if row[COL_NOTE]:
                parts.append(row[COL_NOTE])
            # the ledger is a table, so its links carry \| escapes; a checklist
            # line is plain text and needs the real pipe back
            out.append(MID.join(parts).replace("\\|", "|"))
        out.append("")
    out.append(CHECK_E)
    return out


def parse_ledger(rows):
    cards = []
    for lineno, row in rows:
        if len(row) < NCOL:
            cards.append((lineno, None))
            continue
        cards.append((lineno, row[:NCOL]))
    return cards


def blocker_tokens(lines, lo, hi):
    """Card ids named in the first column of the blocker table."""
    tokens = set()
    for _, row in table_rows(lines, lo, hi):
        text = row[0]
        for m in RANGE.finditer(text):
            prefix, low, other, high = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
            if other and other != prefix:
                continue
            tokens.update("%s%d" % (prefix, n) for n in range(low, high + 1))
        tokens.update(re.findall(r"[A-Z]+[0-9]*", text))
    return tokens


def blocked_elsewhere(tokens, card):
    if card in tokens:
        return True
    pattern = r"(?<![0-9A-Za-z_])%s(?![0-9A-Za-z_])" % re.escape(card)
    return any(re.search(pattern, t) for t in tokens)


def check(cards, tokens):
    errors = []
    seen = {}
    for lineno, row in cards:
        if row is None:
            errors.append("line %d: ledger row has fewer than %d columns" % (lineno, NCOL))
            continue
        card, group, route = row[COL_CARD], row[COL_GROUP], row[COL_ROUTE]
        status, ev = row[COL_STATUS], row[COL_EVIDENCE]
        if not CARD_ID.match(card):
            errors.append("line %d: bad card id %r" % (lineno, card))
        elif card in seen:
            errors.append("%s: duplicated on lines %d and %d" % (card, seen[card], lineno))
        else:
            seen[card] = lineno
        if status not in STATUS:
            errors.append("%s: status %r must be exactly one of %s"
                          % (card, status, " ".join(STATUS)))
        if group not in GROUPS:
            errors.append("%s: group %r must be one of %s" % (card, group, "/".join(GROUPS)))
        if route not in DASHES and not re.match(ROUTE_RE, route):
            errors.append("%s: route %r must be a circled digit or an em dash" % (card, route))
        if row[COL_NOBOARD] not in (NB_YES, NB_PART, NB_NO, ""):
            errors.append("%s: no-board column must be yes / partial / no" % card)
        if not DATE.match(row[COL_UPDATED]):
            errors.append("%s: updated %r is not YYYY-MM-DD" % (card, row[COL_UPDATED]))
        if ev not in DASHES and not EVIDENCE.match(ev):
            errors.append("%s: evidence %r must be 'E<0-6> <pointer>' or an em dash" % (card, ev))
        if status == S_DONE and ev in DASHES:
            errors.append("%s: marked done with no evidence level and pointer" % card)
        if status == S_NA and DECISION not in row[COL_NOTE]:
            errors.append("%s: excluded from the denominator, needs a %sxx id in the note"
                          % (card, DECISION))
        if status == S_BLOCKED and not blocked_elsewhere(tokens, card):
            errors.append("%s: marked blocked but absent from the blocker list" % card)
        if not row[COL_PAGE]:
            errors.append("%s: the detail-page column is empty, so the checklist "
                          "entry would link to nothing" % card)
    return errors


def pct(done, plan):
    return int(round(100.0 * done / plan)) if plan else 0


def summarize(cards):
    """Per-group counters, plus the tally of cards excluded from the denominator."""
    per = {g: dict.fromkeys(list(STATUS.values()) + ["plan"], 0) for g in GROUPS}
    excluded = 0
    for _, row in cards:
        if row is None:
            continue
        stat = per[row[COL_GROUP]]
        if row[COL_STATUS] == S_NA:
            excluded += 1
            continue
        stat["plan"] += 1
        stat[STATUS[row[COL_STATUS]]] += 1
    return per, excluded


def render(per, excluded, cards):
    out = [PROGRESS_B, ""]
    out.append("| %s | %s | %s | %s | %s | %s | %s |" % (L_GROUP, L_PLAN, S_DONE, S_DOING,
                                                         S_BLOCKED, S_TODO, L_RATE))
    out.append("|" + "---|" * 7)
    tot = dict.fromkeys(list(STATUS.values()) + ["plan"], 0)
    for group in GROUPS:
        s = per[group]
        for key in tot:
            tot[key] += s[key]
        out.append("| %s | %d | %d | %d | %d | %d | %d %% |"
                   % (group, s["plan"], s["done"], s["doing"], s["blocked"], s["todo"],
                      pct(s["done"], s["plan"])))
    out.append("| **%s** | **%d** | **%d** | **%d** | **%d** | **%d** | **%d %%** |"
               % (L_TOTAL, tot["plan"], tot["done"], tot["doing"], tot["blocked"], tot["todo"],
                  pct(tot["done"], tot["plan"])))
    dates = [r[COL_UPDATED] for _, r in cards if r and DATE.match(r[COL_UPDATED])]
    out.append("")
    out.append("**%s\uff1a%d / %d = %d %%**%s**%s\uff1a%s**%s**%s\uff08%s\uff09\uff1a%d**"
               % (L_PROGRESS, tot["done"], tot["plan"], pct(tot["done"], tot["plan"]), SEP,
                  L_LATEST, max(dates) if dates else DASHES[0], SEP,
                  L_EXCLUDED, S_NA, excluded))
    out.append("")
    out.append(PROGRESS_E)
    return out, tot


def norm(block):
    """A formatter may pad the generated table, widening cells and the dashed
    separator, to align its columns. Dropping that padding keeps a reformat
    from looking like a content change."""
    out = []
    for line in block:
        out.append(re.sub(r"-{2,}", "-", "".join(line.split())))
    return out


def listing(cards):
    done, open_cards = [], []
    for _, row in cards:
        if row is None:
            continue
        if row[COL_STATUS] == S_DONE:
            done.append(row[COL_CARD])
        elif row[COL_STATUS] != S_NA:
            open_cards.append(row)
    lines = []
    for r in open_cards:
        ev = "" if r[COL_EVIDENCE] in DASHES else "  [%s]" % r[COL_EVIDENCE]
        note = "  " + r[COL_NOTE] if r[COL_NOTE] else ""
        lines.append("%-5s %s %s%s%s" % (r[COL_CARD], r[COL_STATUS], r[COL_NAME], ev, note))
    if done:
        lines.extend(["", "%s %s" % (S_DONE, ", ".join(done))])
    return lines


def apply_tick(lines, lo, hi, card, status, ev):
    """Point one ledger row at a new status without touching the other columns."""
    for i in range(lo, hi + 1):
        if not lines[i].lstrip().startswith("|"):
            continue
        row = cells(lines[i])
        if len(row) < NCOL or row[COL_CARD] != card:
            continue
        row[COL_STATUS] = status
        if ev is not None:
            row[COL_EVIDENCE] = "\u2014" if ev in DASHES else ev
        row[COL_UPDATED] = date.today().isoformat()
        lines[i] = "| " + " | ".join(row) + " |"
        return True
    return False


def parse_tick(args):
    if not 2 <= len(args) <= 3:
        return None
    card, wanted = args[0], args[1]
    status = wanted if wanted in STATUS else STATUS_ALIAS.get(wanted.lower())
    if status is None:
        fail("--tick: bad status %r, use one of %s or todo/doing/blocked/done/na"
             % (wanted, " ".join(STATUS)))
    ev = args[2] if len(args) > 2 else None
    if status == S_DONE and (ev is None or ev in DASHES):
        fail("--tick %s: a done card needs evidence, e.g. "
             "--tick %s done \"E3 sim/run.log\"" % (card, card))
    return card, status, ev


def main(argv):
    flags = [a for a in argv[1:] if a.startswith("--")]
    args = [a for a in argv[1:] if not a.startswith("--")]
    unknown = set(flags) - {"--check", "--list", "--tick"}
    if unknown:
        print(__doc__)
        return 2
    tick_to = parse_tick(args) if "--tick" in flags else None
    if "--tick" in flags and tick_to is None:
        print(__doc__)
        return 2
    positional = [] if tick_to else args
    if len(positional) > 1:
        print(__doc__)
        return 2

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = positional[0] if positional else find_board(root)
    if not os.path.isfile(path):
        fail("not a file: %s" % path)
    here = rel(path, root)

    text, crlf = read(path)
    lines = text.split("\n")
    lb, le = marker_pair(lines, LEDGER_B, LEDGER_E, path)
    bb, be = marker_pair(lines, BLOCK_B, BLOCK_E, path)
    pb, pe = marker_pair(lines, PROGRESS_B, PROGRESS_E, path)

    if tick_to and not apply_tick(lines, lb, le, *tick_to):
        fail("--tick: %s has no row in %s" % (tick_to[0], here))

    cards = parse_ledger(table_rows(lines, lb + 1, le))
    if not cards:
        fail("%s: ledger region has no table rows" % here)

    # The checklist page is optional; when it exists it is regenerated from the
    # ledger, never edited by hand. A page counts only with the marker pair
    # present, so quoting the begin marker in prose is not mistaken for one.
    hits = [p for p in scan_md(root, CHECK_B) if has_markers(p, CHECK_B, CHECK_E)]
    if len(hits) > 1:
        fail("expected at most one page with %s, found: %s"
             % (CHECK_B, ", ".join(hits)))
    cpath = ctext = ccrlf = None
    if hits:
        if os.path.abspath(hits[0]) == os.path.abspath(path):
            fail("%s: put the checklist region on its own page, not on the board"
                 % rel(hits[0], root))
        cpath = hits[0]
        ctext, ccrlf = read(cpath)

    errors = check(cards, blocker_tokens(lines, bb + 1, be))
    if errors:
        print("%s: %d rule violation(s)" % (here, len(errors)))
        for e in errors:
            print("  " + e)
        if tick_to:
            print("  the --tick was not written because the ledger is invalid")
        return 1

    if "--list" in flags:
        for line in listing(cards):
            print(line)
        return 0

    per, excluded = summarize(cards)
    block, tot = render(per, excluded, cards)
    new = lines[:pb] + block + lines[pe + 1:]
    changed = norm(block) != norm(lines[pb:pe + 1])

    cnew = None
    cchanged = False
    if ctext is not None:
        clines = ctext.split("\n")
        cb, ce = marker_pair(clines, CHECK_B, CHECK_E, cpath)
        cblock = render_checklist(cards)
        cnew = clines[:cb] + cblock + clines[ce + 1:]
        cchanged = norm(cblock) != norm(clines[cb:ce + 1])

    if "--check" in flags:
        print("%s: %d/%d = %d %%, %d rule violation(s)"
              % (here, tot["done"], tot["plan"], pct(tot["done"], tot["plan"]), len(errors)))
        stale = []
        if changed:
            stale.append("summary block")
        if cchanged:
            stale.append("checklist block")
        if stale:
            print("  %s is stale, run: python -X utf8 tools/progress.py"
                  % " and ".join(stale))
            return 1
        print("  summary block matches the ledger")
        return 0

    if changed:
        with io.open(path, "w", encoding="utf-8", newline="\r\n" if crlf else "\n") as fh:
            fh.write("\n".join(new))
    if cchanged:
        with io.open(cpath, "w", encoding="utf-8", newline="\r\n" if ccrlf else "\n") as fh:
            fh.write("\n".join(cnew))
    done = []
    if tick_to:
        done.append("ticked %s -> %s" % (tick_to[0], tick_to[1]))
    if changed:
        done.append("summary rewritten")
    if cchanged:
        done.append("checklist rewritten")
    print("%s: %d/%d = %d %%, %d card(s) excluded, %d rule violation(s), %s"
          % (here, tot["done"], tot["plan"], pct(tot["done"], tot["plan"]), excluded,
             len(errors), "; ".join(done) or "already current"))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv))
