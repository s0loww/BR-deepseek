"""Rule checker for 1C sources: the overlay's prose, made executable.

The rules of this distribution have so far only been text an agent may or may
not have read. The mechanically decidable ones do not need reading -- they can
be enforced, for free, before anything reaches a context window.

Two entry points on purpose:

  * a pre-commit gate (`--scope staged`), deterministic and costing no tokens;
  * a manual run with `--json` for any other caller (CI, an agent, a script).

One implementation, two callers. Suppress a deliberate exception with
`airules:allow <rule-id>` on the offending line.

    python rules_check.py --scope staged
    python rules_check.py --scope path --path src/CommonModules
    python rules_check.py --scope diff --base main --json
"""
import argparse
import json
import os
import subprocess
import sys

import bsl
from rules import ERROR, RULES, WARNING

ALLOW_MARKER = "airules:allow"
SEVERITY_ORDER = {ERROR: 0, WARNING: 1}


class Context(object):
    """One file, scanned once and shared by every rule."""

    __slots__ = ("path", "text", "blanked", "routines", "is_form_module")

    def __init__(self, path, text):
        self.path = path
        self.text = text
        self.blanked = bsl.blank_noise(text)
        self.routines = bsl.procedures(self.blanked, self.text)
        normalised = path.replace(os.sep, "/")
        self.is_form_module = "/Forms/" in normalised and normalised.endswith("Module.bsl")


class Violation(object):
    __slots__ = ("path", "line", "rule", "severity", "message", "source", "code")

    def __init__(self, path, line, rule, severity, message, source, code):
        self.path = path
        self.line = line
        self.rule = rule
        self.severity = severity
        self.message = message
        self.source = source
        self.code = code

    def as_dict(self):
        return {"path": self.path, "line": self.line, "rule": self.rule,
                "severity": self.severity, "message": self.message,
                "source": self.source, "code": self.code}

    def as_text(self):
        return "%s:%d [%s] %s %s" % (self.path, self.line, self.rule,
                                     self.severity.upper(), self.message)


def check_file(path, text=None):
    if text is None:
        text = bsl.read_source(path)
    context = Context(path, text)
    lines = text.split(chr(10))
    found = []
    for rule in RULES:
        for line, message in rule["check"](context):
            code = lines[line - 1].strip() if 0 < line <= len(lines) else ""
            if ALLOW_MARKER in code and rule["id"] in code:
                continue
            found.append(Violation(path, line, rule["id"], rule["severity"],
                                   message, rule["source"], code[:200]))
    found.sort(key=lambda v: (SEVERITY_ORDER.get(v.severity, 9), v.path, v.line))
    return found


# --------------------------------------------------------------- file sets

def _git(args, cwd):
    try:
        proc = subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                              text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    return [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]


def collect(scope, root, path=None, base="main"):
    """Which files to check, and whether git was actually available."""
    if scope == "path":
        target = path or root
        if os.path.isfile(target):
            return [target], True
        out = []
        for current, _dirs, files in os.walk(target):
            for name in files:
                if name.endswith(".bsl"):
                    out.append(os.path.join(current, name))
        return sorted(out), True
    if scope == "staged":
        names = _git(["diff", "--cached", "--name-only", "--diff-filter=ACMR"], root)
    else:
        names = _git(["diff", "--name-only", "--diff-filter=ACMR", base + "...HEAD"], root)
    if not names:
        return [], bool(_git(["rev-parse", "--git-dir"], root))
    return [os.path.join(root, name) for name in names
            if name.endswith(".bsl") and os.path.isfile(os.path.join(root, name))], True


# ---------------------------------------------------------------- reporting

def main(argv=None):
    parser = argparse.ArgumentParser(description="Проверка исходников 1С правилами оверлея")
    parser.add_argument("--scope", choices=("staged", "path", "diff"), default="staged")
    parser.add_argument("--path", help="файл или каталог для --scope path")
    parser.add_argument("--base", default="main", help="база сравнения для --scope diff")
    parser.add_argument("--root", default=".", help="корень проекта")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--warnings-as-errors", action="store_true")
    parser.add_argument("--list-rules", action="store_true")
    args = parser.parse_args(argv)

    if args.list_rules:
        for rule in RULES:
            print("%-30s %-7s %s" % (rule["id"], rule["severity"], rule["source"]))
        return 0

    root = os.path.abspath(args.root)
    files, git_ok = collect(args.scope, root, args.path, args.base)

    violations = []
    unreadable = []
    for path in files:
        try:
            violations.extend(check_file(path))
        except OSError as exc:
            unreadable.append("%s: %s" % (path, exc))

    for violation in violations:
        violation.path = os.path.relpath(violation.path, root).replace(os.sep, "/")

    errors = [v for v in violations if v.severity == ERROR]
    warnings = [v for v in violations if v.severity == WARNING]
    failed = bool(errors) or (args.warnings_as_errors and bool(warnings))

    if args.as_json:
        json.dump({"scope": args.scope, "files": len(files), "git": git_ok,
                   "violations": [v.as_dict() for v in violations],
                   "unreadable": unreadable, "failed": failed},
                  sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 1 if failed else 0

    if not files:
        print("проверять нечего" + ("" if git_ok else " (git недоступен — укажите --scope path)"))
        return 0
    for violation in violations:
        print(violation.as_text())
    for note in unreadable:
        print("не прочитан " + note, file=sys.stderr)
    print()
    print("файлов: %d, ошибок: %d, предупреждений: %d"
          % (len(files), len(errors), len(warnings)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
