"""Build integrity checks. Run: python ci/check.py"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import assemble  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OVERLAYS = sorted(p for p in (ROOT / "overlays").glob("*") if p.is_dir())
ERRORS = []

# Kun's built-in tool names (Settings → Agents → permissions). Everything else
# in allowedTools / blockedTools would be silently ignored.
KUN_BUILTIN_TOOLS = {"read", "grep", "find", "ls", "repo_map", "git_inspect", "edit",
                     "write", "bash", "lsp", "verify_changes", "send_im_attachment"}


def err(msg):
    ERRORS.append(msg)


def rel(path):
    return path.relative_to(ROOT).as_posix()


def frontmatter(path):
    t = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", t, re.S)
    return (m.group(1) if m else None), t


def rule_names(rules_dir):
    return {p.name for p in rules_dir.glob("*.md")}


BASE_RULES = rule_names(ROOT / "rules")


def check_role_frontmatter():
    """A role must carry the fields Kun actually reads."""
    required = {"id", "name", "description", "mode", "toolPolicy"}
    allowed = required | {"color", "systemPrompt", "promptPreamble",
                          "allowedTools", "blockedTools"}
    dirs = [(ROOT / "agents/roles", False)] + [(o / "agents/roles", True) for o in OVERLAYS]
    for roles_dir, is_overlay in dirs:
        for f in sorted(roles_dir.glob("*.md")):
            name = rel(f)
            fm, _ = frontmatter(f)
            if fm is None:
                err(f"{name}: no frontmatter")
                continue
            keys = {m.group(1) for m in re.finditer(r"^([A-Za-z]+):", fm, re.M)}
            for miss in sorted(required - keys):
                err(f"{name}: missing required field '{miss}'")
            for extra in sorted(keys - allowed):
                err(f"{name}: field '{extra}' is not read by Kun")
            idm = re.search(r"^id:\s*(\S+)$", fm, re.M)
            if idm and idm.group(1) != f.stem:
                err(f"{name}: id '{idm.group(1)}' does not match the file name")
            pol = re.search(r"^toolPolicy:\s*(\S+)$", fm, re.M)
            if pol and pol.group(1) not in ("readOnly", "inherit"):
                err(f"{name}: toolPolicy '{pol.group(1)}' outside {{readOnly, inherit}}")
            if pol and pol.group(1) == "readOnly" and is_overlay:
                err(f"{name}: readOnly strips MCP and skills in Kun — an overlay role "
                    f"loses the overlay's MCP; use inherit + blockedTools")
            desc = re.search(r'^description:\s*"?(.*?)"?\s*$', fm, re.M)
            if desc and len(desc.group(1)) > 1024:
                err(f"{name}: description longer than Kun's 1024-character limit")
            for field in ("allowedTools", "blockedTools"):
                lm = re.search(rf"^{field}:\s*\[(.*)\]\s*$", fm, re.M)
                if field in keys and not lm:
                    err(f"{name}: {field} must be an inline list [\"a\", \"b\"]")
                    continue
                if lm:
                    tools = {t.strip().strip("\"'") for t in lm.group(1).split(",") if t.strip()}
                    for bad in sorted(tools - KUN_BUILTIN_TOOLS):
                        err(f"{name}: {field} names '{bad}', which is not a Kun built-in tool")


def check_skill_frontmatter():
    for skills_dir in [ROOT / "skills"] + [o / "skills" for o in OVERLAYS]:
        for f in sorted(skills_dir.glob("*/SKILL.md")):
            fm, _ = frontmatter(f)
            if fm is None:
                err(f"{rel(f)}: no frontmatter")
                continue
            for field in ("id", "name", "description"):
                if not re.search(rf"^{field}:", fm, re.M):
                    err(f"{rel(f)}: missing field '{field}'")
            idm = re.search(r"^id:\s*(\S+)$", fm, re.M)
            if idm and idm.group(1) != f.parent.name:
                err(f"{rel(f)}: id '{idm.group(1)}' does not match the directory name")


RULE_REF = re.compile(r"`(?:rules/)?([a-z0-9-]+\.md)`")


def check_rule_links():
    """A `foo.md` reference must resolve among the rules installed next to it.

    Base rules install alone, so they may not point into an overlay; overlay
    rules and roles install on top of the base and may point at both."""
    for f in sorted((ROOT / "rules").glob("*.md")):
        for m in RULE_REF.finditer(f.read_text(encoding="utf-8")):
            if m.group(1) not in BASE_RULES:
                err(f"{rel(f)}: reference to a rule missing from the base: {m.group(1)}")
    for o in OVERLAYS:
        present = BASE_RULES | rule_names(o / "rules")
        files = sorted((o / "rules").glob("*.md")) + sorted((o / "agents/roles").glob("*.md"))
        for f in files:
            for m in RULE_REF.finditer(f.read_text(encoding="utf-8")):
                if m.group(1) not in present:
                    err(f"{rel(f)}: reference to a missing rule {m.group(1)}")


def indexed_rules(contract_path):
    return set(re.findall(r"`rules/([a-z0-9-]+\.md)`\s*\|", contract_path.read_text(encoding="utf-8")))


def check_index_coverage():
    """Every contract template indexes exactly the rules installed with it."""
    pairs = [(ROOT / "templates/AGENTS.md", BASE_RULES)]
    pairs += [(o / "templates/AGENTS.md", BASE_RULES | rule_names(o / "rules")) for o in OVERLAYS
              if (o / "templates/AGENTS.md").exists()]
    for contract, present in pairs:
        indexed = indexed_rules(contract)
        for orphan in sorted(present - indexed):
            err(f"{rel(contract)}: rule {orphan} is absent from the Rule Index — it will never load")
        for missing in sorted(indexed - present):
            err(f"{rel(contract)}: Rule Index points at a missing {missing}")


def check_assembled():
    """Generated overlay contracts must match base template + fragment."""
    base = assemble.BASE.read_text(encoding="utf-8")
    for frag, gen in assemble.targets():
        try:
            text = assemble.assemble(base, frag.read_text(encoding="utf-8"))
        except ValueError as exc:
            err(f"{rel(frag)}: {exc}")
            continue
        if not gen.exists() or gen.read_text(encoding="utf-8") != text:
            err(f"{rel(gen)}: out of date — run python ci/assemble.py")


PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")


def placeholder_homes():
    homes = {"templates/AGENTS.md", "INSTALL.md"}
    for o in OVERLAYS:
        homes |= {rel(p) for p in (o / "templates").glob("*.md")}
        homes.add(rel(o / "README.md"))
    return homes


def check_placeholders():
    """Contract placeholders stay in contract templates, and each one is documented.

    Only the names the templates declare count: skill and tool docs carry
    their own `{{…}}` (a generated form's fields, a deploy profile's values),
    which are filled at run time, not at installation."""
    templates = [ROOT / "templates/AGENTS.md"] + [o / "templates/AGENTS.md" for o in OVERLAYS]
    declared = set()
    for t in templates:
        if t.exists():
            declared |= set(PLACEHOLDER.findall(t.read_text(encoding="utf-8")))
    homes = placeholder_homes()
    for f in sorted(ROOT.rglob("*.md")):
        r = rel(f)
        if r in homes or r.startswith(".git/"):
            continue
        leaked = sorted(set(PLACEHOLDER.findall(f.read_text(encoding="utf-8"))) & declared)
        if leaked:
            err(f"{r}: contract placeholder outside the template: {', '.join(leaked)}")
    docs = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
    docs += "".join((o / "README.md").read_text(encoding="utf-8")
                    for o in OVERLAYS if (o / "README.md").exists())
    for ph in sorted(declared - set(PLACEHOLDER.findall(docs))):
        err(f"placeholder {{{{{ph}}}}} is not explained in INSTALL.md or an overlay README")


TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".py", ".ps1", ".psm1", ".toml", ".txt", ".log", ".xml"}


def text_files():
    for f in sorted(ROOT.rglob("*")):
        r = rel(f)
        if (not f.is_file() or f.suffix.lower() not in TEXT_SUFFIXES or r == "ci/check.py"
                or r.startswith((".git/", "docs/internal/")) or "__pycache__" in f.parts):
            continue
        yield f, r


def check_foreign_paths():
    """The target layout is .kun/, not .claude/."""
    for f, r in text_files():
        if r.startswith(("docs/", "install/")) or r == "README.md" or r.endswith("THIRD-PARTY.md"):
            continue  # these files legitimately describe neighbouring harnesses
        for m in re.finditer(r"\.claude/\S*", f.read_text(encoding="utf-8", errors="replace")):
            err(f"{r}: foreign-harness path {m.group(0)}")


MACHINE = re.compile(r"[A-Za-z]:[\\/](?:Users[\\/](?!<)|AI_Projects|Work[\\/])|dev-main|\.ts\.net\b|\b100\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")


def check_machine_specifics():
    """The repository is public: no machine paths, host names or tailnet addresses."""
    for f, r in text_files():
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            m = MACHINE.search(line)
            if m:
                err(f"{r}:{i}: machine-specific value '{m.group(0)}'")


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


# Kun's project config schema is strict: an unknown key makes the whole file
# invalid and Kun silently runs the project without its MCP servers.
PROJECT_KEYS = {"$schema", "version", "mcp", "skills"}
SERVER_KEYS = {"enabled", "transport", "command", "args", "cwd", "url", "headers", "env",
               "oauth", "timeoutMs"}
SKILLS_KEYS = {"enabled", "includeConventional", "roots", "disabledIds"}
RLM_MAX_EXECUTION_MS = 300_000  # rlm_execute: execution_timeout_seconds maximum


def check_project_configs():
    for f in sorted(ROOT.glob("overlays/*/templates/project*.json")):
        name = rel(f)
        try:
            cfg = json.loads(f.read_text(encoding="utf-8"))
        except ValueError as exc:
            err(f"{name}: not JSON — {exc}")
            continue
        for extra in sorted(set(cfg) - PROJECT_KEYS):
            err(f"{name}: key '{extra}' is not in Kun's project schema")
        if cfg.get("version") != 1:
            err(f"{name}: version must be 1")
        for extra in sorted(set(cfg.get("skills", {})) - SKILLS_KEYS):
            err(f"{name}: skills.{extra} is not in Kun's project schema")
        for sid, srv in cfg.get("mcp", {}).get("servers", {}).items():
            where = f"{name}: server '{sid}'"
            for extra in sorted(set(srv) - SERVER_KEYS):
                err(f"{where}: key '{extra}' is not in Kun's schema")
            transport = srv.get("transport")
            if transport not in ("stdio", "streamable-http", "sse"):
                err(f"{where}: transport {transport!r} outside stdio | streamable-http | sse")
            if transport == "stdio" and not srv.get("command"):
                err(f"{where}: stdio needs command")
            if transport in ("streamable-http", "sse") and not srv.get("url"):
                err(f"{where}: {transport} needs url")
            if "cwd" in srv and (transport != "stdio" or re.match(r"^([A-Za-z]:|/|\\)", srv["cwd"])
                                 or ".." in srv["cwd"]):
                err(f"{where}: cwd is stdio-only and must be relative inside the workspace")
            timeout = srv.get("timeoutMs", 30_000)
            if not isinstance(timeout, int) or not 0 < timeout <= 600_000:
                err(f"{where}: timeoutMs must be an integer in (0, 600000]")
            elif sid == "rlm" and timeout <= RLM_MAX_EXECUTION_MS:
                err(f"{where}: timeoutMs {timeout} does not cover rlm_execute's own maximum "
                    f"of {RLM_MAX_EXECUTION_MS} ms — Kun would cut long calls (its default is 30000)")


for check in (check_role_frontmatter, check_skill_frontmatter, check_rule_links,
              check_index_coverage, check_assembled, check_placeholders,
              check_foreign_paths, check_machine_specifics, check_model_map,
              check_project_configs):
    check()

if ERRORS:
    print(f"FAIL: {len(ERRORS)}")
    for e in ERRORS:
        print(" -", e)
    sys.exit(1)
print("OK: build is consistent")
