"""Assemble overlay contract templates: base templates/AGENTS.md + overlay fragment.

    python ci/assemble.py          # write overlays/<stack>/templates/AGENTS.md
    python ci/assemble.py --check  # exit 1 if a generated file is out of date

A fragment `overlays/<stack>/templates/AGENTS.<stack>.md` carries blocks under
markers; anything before the first marker is ignored:

    <!-- after: ## Heading -->    insert the block after that section
    <!-- replace: ## Heading -->  replace that section with the block

The generated file is committed on purpose: installing onto a project is a
copy of one file, not a merge by hand.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "templates" / "AGENTS.md"
MARKER = re.compile(r"^<!-- (after|replace): (## .+?) -->$", re.M)


def _section(body):
    body = body.strip("\n") + "\n\n"
    return [body.splitlines()[0] if body.startswith("## ") else None, body]


def split_sections(text):
    """[[heading or None, body]] — the body includes its heading line."""
    return [_section(p) for p in re.split(r"(?m)^(?=## )", text) if p.strip()]


def parse_fragment(text):
    marks = list(MARKER.finditer(text))
    blocks = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        blocks.append((m.group(1), m.group(2), text[m.end():end]))
    return blocks


def assemble(base, fragment):
    sections = split_sections(base)
    for op, heading, body in parse_fragment(fragment):
        hits = [i for i, (h, _) in enumerate(sections) if h == heading]
        if len(hits) != 1:
            raise ValueError(f"marker '{heading}' matches {len(hits)} sections of the base template")
        i = hits[0]
        if op == "replace":
            sections[i] = _section(body)
        else:
            sections.insert(i + 1, _section(body))
    return "".join(body for _, body in sections).rstrip("\n") + "\n"


def targets():
    """[(fragment, generated)] for every overlay that has a fragment."""
    out = []
    for frag in sorted((ROOT / "overlays").glob("*/templates/AGENTS.*.md")):
        out.append((frag, frag.parent / "AGENTS.md"))
    return out


def main(argv):
    check = "--check" in argv
    base = BASE.read_text(encoding="utf-8")
    stale = 0
    for frag, gen in targets():
        text = assemble(base, frag.read_text(encoding="utf-8"))
        rel = gen.relative_to(ROOT).as_posix()
        current = gen.read_text(encoding="utf-8") if gen.exists() else None
        if check:
            if current != text:
                print(f"out of date: {rel} — run python ci/assemble.py")
                stale += 1
        elif current != text:
            gen.write_text(text, encoding="utf-8", newline="\n")
            print(f"written: {rel}")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
