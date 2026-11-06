import glob
import os
import sys

PATTERNS_DEFAULT = ["*.md", "*.mmd"]
BOM = b"\xef\xbb\xbf"


def expand(paths):
    patterns = [p for p in paths if not os.path.isdir(p)]
    dirs = [p for p in paths if os.path.isdir(p)]
    bases = [os.path.basename(p) for p in patterns] if patterns else list(PATTERNS_DEFAULT)
    files = [match for pattern in patterns for match in glob.glob(pattern)]
    for directory in dirs:
        for base in bases:
            files.extend(glob.glob(os.path.join(directory, "**", base), recursive=True))
    return sorted(set(f for f in files if os.path.isfile(f)))


def main():
    args = sys.argv[1:]
    check = "--check" in args
    targets = [a for a in args if not a.startswith("--")] or PATTERNS_DEFAULT

    files = expand(targets)
    changed = []
    non_utf8 = []

    for path in files:
        data = open(path, "rb").read()
        probe = data[3:] if data.startswith(BOM) else data
        try:
            probe.decode("utf-8")
        except UnicodeDecodeError:
            non_utf8.append(path)
        fixed = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        if fixed.startswith(BOM):
            fixed = fixed[len(BOM):]
        if fixed != data:
            changed.append((path, data.count(b"\r\n"), len(data) - len(fixed)))
            if not check:
                open(path, "wb").write(fixed)

    for path, crlfs, delta in changed:
        print("CRLF " + str(crlfs) + "  " + path)
    for path in non_utf8:
        print("NOT-UTF8  " + path)

    print("---")
    print(str(len(files)) + " files scanned, " + str(len(changed)) + (" would change" if check else " changed")
          + ", " + str(len(non_utf8)) + " not utf-8")
    return 1 if non_utf8 else 0


if __name__ == "__main__":
    sys.exit(main())
