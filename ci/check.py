"""Build integrity checks. Run: python ci/check.py"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ERRORS = []


def err(msg):
    ERRORS.append(msg)


def frontmatter(path):
    t = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", t, re.S)
    return (m.group(1) if m else None), t


def check_role_frontmatter():
    """A role must carry the fields Kun actually reads."""
    required = {"id", "name", "description", "mode", "toolPolicy"}
    allowed = required | {"color", "systemPrompt", "promptPreamble",
                          "allowedTools", "blockedTools"}
    for f in sorted((ROOT / "agents/roles").glob("*.md")):
        fm, _ = frontmatter(f)
        if fm is None:
            err(f"{f.name}: no frontmatter")
            continue
        keys = {m.group(1) for m in re.finditer(r"^([A-Za-z]+):", fm, re.M)}
        for miss in sorted(required - keys):
            err(f"{f.name}: missing required field '{miss}'")
        for extra in sorted(keys - allowed):
            err(f"{f.name}: field '{extra}' is not read by Kun")
        idm = re.search(r"^id:\s*(\S+)$", fm, re.M)
        if idm and idm.group(1) != f.stem:
            err(f"{f.name}: id '{idm.group(1)}' does not match the file name")
        pol = re.search(r"^toolPolicy:\s*(\S+)$", fm, re.M)
        if pol and pol.group(1) not in ("readOnly", "inherit"):
            err(f"{f.name}: toolPolicy '{pol.group(1)}' outside {{readOnly, inherit}}")


def check_skill_frontmatter():
    for f in sorted((ROOT / "skills").glob("*/SKILL.md")):
        fm, _ = frontmatter(f)
        if fm is None:
            err(f"skills/{f.parent.name}: no frontmatter")
            continue
        for field in ("id", "name", "description"):
            if not re.search(rf"^{field}:", fm, re.M):
                err(f"skills/{f.parent.name}: missing field '{field}'")


def check_rule_links():
    """A `foo.md` reference inside rules/ must point at a file that exists."""
    present = {p.name for p in (ROOT / "rules").glob("*.md")}
    for f in sorted((ROOT / "rules").glob("*.md")):
        for m in re.finditer(r"`([a-z0-9-]+\.md)`", f.read_text(encoding="utf-8")):
            if m.group(1) not in present:
                err(f"rules/{f.name}: reference to a missing rule {m.group(1)}")


def check_index_coverage():
    """The contract template index and the rule files must match one to one."""
    contract = (ROOT / "templates/AGENTS.md").read_text(encoding="utf-8")
    indexed = set(re.findall(r"`rules/([a-z0-9-]+\.md)`", contract))
    present = {p.name for p in (ROOT / "rules").glob("*.md")}
    for orphan in sorted(present - indexed):
        err(f"rule {orphan} is absent from the Rule Index — it will never load")
    for missing in sorted(indexed - present):
        err(f"Rule Index points at a missing {missing}")


def check_placeholders():
    """Placeholders are allowed only in the contract template."""
    for f in sorted(ROOT.rglob("*.md")):
        if f.relative_to(ROOT).as_posix() in ("templates/AGENTS.md", "INSTALL.md"):
            continue
        if "{{" in f.read_text(encoding="utf-8"):
            err(f"{f.relative_to(ROOT)}: unfilled placeholder outside the template")


def check_foreign_paths():
    """The target layout is .kun/, not .claude/."""
    for f in sorted(ROOT.rglob("*.md")):
        rel = f.relative_to(ROOT).as_posix()
        if rel.startswith(("docs/", "install/")) or rel == "README.md":
            continue  # these files legitimately describe neighbouring harnesses
        for m in re.finditer(r"\.claude/\S*", f.read_text(encoding="utf-8")):
            err(f"{rel}: foreign-harness path {m.group(0)}")


def check_model_map():
    """The map must parse, and `off` must survive as a string, not a YAML boolean."""
    import yaml
    m = yaml.safe_load((ROOT / "install/model-map.yaml").read_text(encoding="utf-8"))
    if "off" not in m["efforts"]:
        err("model-map: 'off' is not a string in `efforts` — quote it (YAML 1.1 reads bare off as false)")
    mech = m["deepseek"]["effort"]["mechanical"]
    if mech != "off":
        err(f"model-map: effort.mechanical is {mech!r}, expected the string 'off'")
    for tier in ("pro", "flash"):
        if not str(m["deepseek"].get(tier, "")).startswith("deepseek-"):
            err(f"model-map: tier '{tier}' does not resolve to a deepseek model")


for check in (check_role_frontmatter, check_skill_frontmatter, check_rule_links,
              check_index_coverage, check_placeholders, check_foreign_paths,
              check_model_map):
    check()

if ERRORS:
    print(f"FAIL: {len(ERRORS)}")
    for e in ERRORS:
        print(" -", e)
    sys.exit(1)
print("OK: build is consistent")
