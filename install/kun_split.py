#!/usr/bin/env python3
"""Проверка установленного 1С-проекта и разведение совмещённой раскладки.

    python install/kun_split.py verify <P> <B> [--out отчёт.json]
    python install/kun_split.py inventory <X> [--out отчёт.json]
    python install/kun_split.py carry <X> <P> [--apply] [--with-build-edits | --skip-build-edits]
                                              [--include ПУТЬ ...] [--out отчёт.json]

P — папка проекта, B — клон сборки, X — папка, где проект поставлен прямо в
клон сборки (так делать не надо; как развести — install/split-layout.md).

verify — проверка после каждой установки и обновления сборки. Рассчитана на
проект с оверлеем 1С: базу без оверлея она сочтёт неполной.

inventory  только читает X и раскладывает каждый файл по категориям:
           файл сборки, поставлен из сборки без правок / с правками, файл
           проекта, игнорируемый git. Чей файл — решает сравнение содержимого
           с источником в сборке, а не имя.
carry      копирует из X в P то, что принадлежит проекту: файлы проекта и
           поставленные файлы, которые в проекте правили. По умолчанию — план
           без записи; запись — только с --apply, после записи каждая копия
           сверяется с источником по хешу.
verify     проверяет установленный проект P против сборки B.

X не меняется ни одной командой. Содержимое файлов не печатается — только
пути и хеши, поэтому скрипт безопасен для .dev.env и профилей с кредами.

Коды выхода: 0 — всё в порядке; 1 — есть что решить человеку (изменённые файлы
сборки, конфликты, непройденная проверка); 2 — ошибка входа.

Только стандартная библиотека, Python 3.8+.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from collections import Counter, OrderedDict
from pathlib import Path

BUILD = "файл сборки"
BUILD_MODIFIED = "файл сборки, изменён локально"
BUILD_DELETED = "файл сборки, удалён локально"
INSTALLED = "поставлен из сборки, без правок"
INSTALLED_EDITED = "поставлен из сборки, изменён в проекте"
PROJECT = "файл проекта"
IGNORED_BUILD = "игнорируется git, служебный файл сборки"
JUNK = "кэш"
IGNORED_OTHER = "игнорируется git — решить, нужен ли проекту"

ORDER = [BUILD_MODIFIED, BUILD_DELETED, PROJECT, INSTALLED_EDITED, IGNORED_OTHER,
         INSTALLED, BUILD, IGNORED_BUILD, JUNK]
SENSITIVE = re.compile(r"(^|/)(\.dev\.env|\.env[^/]*|agent-1c\.json)$", re.I)
KUN_PROJECT_KEYS = {"$schema", "version", "mcp", "skills"}
KUN_SERVER_KEYS = {"enabled", "transport", "command", "args", "cwd", "url", "headers", "env",
                   "oauth", "timeoutMs"}


class InputError(Exception):
    pass


def digest(path):
    """Хеш содержимого без учёта концов строк: autocrlf мог переписать копию."""
    data = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def git(repo, *args):
    proc = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True)
    if proc.returncode != 0:
        raise InputError(f"git {' '.join(args)}: {proc.stderr.decode('utf-8', 'replace').strip()}")
    return proc.stdout


def require_build(root, what):
    if not (root / "overlays/1c/README.md").is_file() or not (root / "templates/AGENTS.md").is_file():
        raise InputError(f"{what} {root} не похож на сборку BR-deepseek (нет overlays/1c/README.md)")


def install_sources(rel):
    """Откуда в сборке берётся файл, поставленный по overlays/1c/README.md."""
    p = rel.split("/")
    if rel == ".kun/project.json":
        return ["overlays/1c/templates/project.json", "overlays/1c/templates/project.stdio.json"]
    if rel == ".dev.env.example":
        return ["overlays/1c/dev.env.example"]
    if p[0] == "rules" and len(p) == 2:
        return [f"overlays/1c/rules/{p[1]}", f"rules/{p[1]}"]
    if p[:2] == [".kun", "agents"] and len(p) == 3:
        return [f"overlays/1c/agents/roles/{p[2]}", f"agents/roles/{p[2]}"]
    if p[:2] == [".kun", "skills"] and len(p) >= 3:
        rest = "/".join(p[2:])
        return [f"overlays/1c/skills/{rest}", f"skills/{rest}"]
    if p[0] == "tools" and len(p) >= 2:
        return ["overlays/1c/tools/" + "/".join(p[1:])]
    return []


def expand(root, rel):
    path = root / rel
    if path.is_dir():
        return sorted(f.relative_to(root).as_posix() for f in path.rglob("*") if f.is_file())
    return [rel.rstrip("/")] if path.is_file() else []


def inventory(x):
    require_build(x, "папка")
    raw = git(x, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignored=matching")
    parts = raw.decode("utf-8").split("\0")
    modified, deleted, untracked, ignored = set(), set(), [], []
    i = 0
    while i < len(parts):
        entry = parts[i]
        i += 1
        if len(entry) < 4:
            continue
        code, rel = entry[:2], entry[3:]
        if code[0] in "RC":
            i += 1  # у переименования следом идёт старый путь
        if code == "??":
            untracked.append(rel)
        elif code == "!!":
            ignored.append(rel)
        elif "D" in code:
            deleted.add(rel)
        else:
            modified.add(rel)
    tracked = [t for t in git(x, "ls-files", "-z").decode("utf-8").split("\0") if t]

    files = OrderedDict()
    for rel in tracked:
        files[rel] = {"category": BUILD_DELETED if rel in deleted else
                      BUILD_MODIFIED if rel in modified else BUILD}
    for entry in untracked:
        for rel in expand(x, entry):
            if rel == "AGENTS.md":
                files[rel] = {"category": PROJECT, "note": "заполненный контракт проекта"}
                continue
            # В совмещённой раскладке кандидат rules/<имя> — это сам файл: он
            # всегда «совпал бы с источником» и прятал бы правку проекта.
            present = [s for s in install_sources(rel) if s != rel and (x / s).is_file()]
            if not present:
                files[rel] = {"category": PROJECT}
                continue
            mine = digest(x / rel)
            same = [s for s in present if digest(x / s) == mine]
            files[rel] = ({"category": INSTALLED, "source": same[0]} if same else
                          {"category": INSTALLED_EDITED, "source": present[0]})
    for entry in ignored:
        for rel in expand(x, entry):
            if rel == ".env" or rel.startswith("docs/internal/"):
                cat = IGNORED_BUILD
            elif "__pycache__" in rel.split("/") or rel.endswith(".pyc"):
                cat = JUNK
            else:
                cat = IGNORED_OTHER
            files[rel] = {"category": cat}
    for rel, info in files.items():
        if SENSITIVE.search(rel):
            info["sensitive"] = True

    origin = git(x, "remote", "get-url", "origin").decode("utf-8").strip() if _has_origin(x) else ""
    head = git(x, "log", "-1", "--format=%h %s").decode("utf-8").strip()
    version = (x / "VERSION").read_text(encoding="utf-8").strip() if (x / "VERSION").is_file() else ""
    return {"root": str(x), "origin": origin, "head": head, "version": version, "files": files}


def _has_origin(repo):
    return subprocess.run(["git", "-C", str(repo), "remote", "get-url", "origin"],
                          capture_output=True).returncode == 0


def grouped(paths, limit=40):
    """Длинный список сворачивается до каталогов с числом файлов."""
    if len(paths) <= limit:
        return paths
    counter = Counter("/".join(p.split("/")[:2]) + ("/…" if p.count("/") >= 2 else "") for p in paths)
    return [f"{k}  ({n} файл.)" for k, n in sorted(counter.items())]


def print_inventory(inv):
    print(f"Папка: {inv['root']}")
    print(f"Сборка: версия {inv['version']}, коммит {inv['head']}, origin {inv['origin'] or '(нет)'}")
    by_cat = OrderedDict((c, []) for c in ORDER)
    for rel, info in inv["files"].items():
        by_cat[info["category"]].append(rel)
    print("\n## Сводка\n")
    for cat, paths in by_cat.items():
        print(f"- {cat}: {len(paths)}")
    for cat in (BUILD_MODIFIED, BUILD_DELETED, PROJECT, INSTALLED_EDITED, IGNORED_OTHER):
        if not by_cat[cat]:
            continue
        print(f"\n## {cat}\n")
        for line in grouped(by_cat[cat]):
            info = inv["files"].get(line, {})
            tail = []
            if info.get("note"):
                tail.append(info["note"])
            if info.get("source"):
                tail.append(f"источник {info['source']}")
            if info.get("sensitive"):
                tail.append("СЕКРЕТЫ: содержимое не выводить")
            print(f"- {line}" + (f"  — {'; '.join(tail)}" if tail else ""))
    need_human = bool(by_cat[BUILD_MODIFIED] or by_cat[BUILD_DELETED] or by_cat[IGNORED_OTHER])
    if need_human:
        print("\nЕсть что решить человеку: изменённые/удалённые файлы сборки или игнорируемые файлы.")
    return 1 if need_human else 0


def carry(x, p, args):
    inv = inventory(x)
    if not (p / "rules").is_dir() or not (p / ".kun/agents").is_dir():
        raise InputError(f"в {p} нет rules/ и .kun/agents/ — сначала поставить сборку по overlays/1c/README.md")
    if p.resolve() == x.resolve() or x.resolve() in p.resolve().parents:
        raise InputError("папка проекта не может быть X или лежать внутри X")
    build_edits = [r for r, i in inv["files"].items() if i["category"] == BUILD_MODIFIED]
    if build_edits and not (args.with_build_edits or args.skip_build_edits):
        raise InputError(f"в X изменено файлов сборки: {len(build_edits)} — выбрать "
                         f"--with-build-edits или --skip-build-edits (см. inventory)")
    include = [i.replace("\\", "/").rstrip("/") for i in args.include]

    plan = []
    for rel, info in inv["files"].items():
        cat = info["category"]
        overwrite = False
        if cat == PROJECT:
            overwrite = rel == "AGENTS.md"
        elif cat == INSTALLED_EDITED:
            overwrite = True
        elif cat == BUILD_MODIFIED and args.with_build_edits:
            overwrite = True
        elif cat == IGNORED_OTHER and any(rel == i or rel.startswith(i + "/") for i in include):
            overwrite = False
        else:
            continue
        plan.append((rel, cat, overwrite))

    rows, conflicts, copied = [], 0, 0
    for rel, cat, overwrite in plan:
        src, dst = x / rel, p / rel
        if dst.exists():
            if digest(dst) == digest(src):
                action = "уже есть такой же"
            elif overwrite:
                action = "перезаписать"
            else:
                action = "КОНФЛИКТ: в P уже другой файл, не трогаю"
                conflicts += 1
        else:
            action = "скопировать"
        row = {"path": rel, "category": cat, "action": action}
        if args.apply and action in ("скопировать", "перезаписать"):
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            row["verified"] = digest(dst) == digest(src)
            if not row["verified"]:
                conflicts += 1
            copied += 1
        rows.append(row)

    counts = Counter(r["action"] for r in rows)
    print(f"{'ЗАПИСЬ' if args.apply else 'ПЛАН (без записи, для записи --apply)'}: {x} -> {p}")
    for action, n in counts.most_common():
        print(f"- {action}: {n}")
    for r in rows:
        if r["action"] != "уже есть такой же":
            mark = "" if "verified" not in r else ("  [сверено]" if r["verified"] else "  [НЕ СОВПАЛО]")
            print(f"  {r['action']}: {r['path']}  ({r['category']}){mark}")
    skipped = [r for r, i in inv["files"].items() if i["category"] == IGNORED_OTHER
               and not any(r == inc or r.startswith(inc + "/") for inc in include)]
    if skipped:
        print(f"\nНе переносятся (игнорируются git, не указаны в --include): {len(skipped)}")
        for line in grouped(skipped, 15):
            print(f"  {line}")
    if args.apply:
        print(f"\nскопировано {copied}, расхождений после копирования и конфликтов: {conflicts}")
    return {"plan": rows, "conflicts": conflicts, "applied": args.apply}, (1 if conflicts else 0)


def verify(p, b):
    require_build(b, "сборка")
    if (p / "overlays/1c").exists() or (p / "ci/check.py").exists():
        raise InputError(f"{p} снова выглядит как клон сборки — проект должен лежать отдельно")
    fails, notes = [], []
    contract = p / "AGENTS.md"
    if not contract.is_file():
        fails.append("нет AGENTS.md")
    else:
        text = contract.read_text(encoding="utf-8")
        left = sorted(set(re.findall(r"\{\{([A-Z_]+)\}\}", text)))
        if left:
            fails.append("незаполненные плейсхолдеры в AGENTS.md: " + ", ".join(left))
        indexed = set(re.findall(r"`rules/([a-z0-9-]+\.md)`\s*\|", text))
        present = {f.name for f in (p / "rules").glob("*.md")}
        for orphan in sorted(present - indexed):
            fails.append(f"rules/{orphan} нет в индексе AGENTS.md — агент его не прочитает")
        for missing in sorted(indexed - present):
            fails.append(f"индекс AGENTS.md ссылается на отсутствующий rules/{missing}")
        expected = {f.name for f in (b / "rules").glob("*.md")} | {f.name for f in (b / "overlays/1c/rules").glob("*.md")}
        for miss in sorted(expected - present):
            fails.append(f"не поставлено правило сборки rules/{miss}")

    roles = {f.stem for f in (b / "agents/roles").glob("*.md")} | {f.stem for f in (b / "overlays/1c/agents/roles").glob("*.md")}
    have = {f.stem for f in (p / ".kun/agents").glob("*.md")}
    for miss in sorted(roles - have):
        fails.append(f"нет роли .kun/agents/{miss}.md")
    skills = [d.name for base in (b / "skills", b / "overlays/1c/skills") for d in base.iterdir() if (d / "SKILL.md").is_file()]
    for s in sorted(skills):
        if not (p / ".kun/skills" / s / "SKILL.md").is_file():
            fails.append(f"нет скилла .kun/skills/{s}/SKILL.md")
    for t in sorted(d.name for d in (b / "overlays/1c/tools").iterdir() if d.is_dir()):
        if not (p / "tools" / t).is_dir():
            fails.append(f"нет инструмента tools/{t}")

    pj = p / ".kun/project.json"
    if not pj.is_file():
        fails.append("нет .kun/project.json")
    else:
        try:
            cfg = json.loads(pj.read_text(encoding="utf-8"))
            extra = set(cfg) - KUN_PROJECT_KEYS
            if extra or cfg.get("version") != 1:
                fails.append(f".kun/project.json: version должен быть 1, лишние ключи {sorted(extra)}")
            for sid, srv in cfg.get("mcp", {}).get("servers", {}).items():
                bad = set(srv) - KUN_SERVER_KEYS
                if bad:
                    fails.append(f".kun/project.json: у сервера {sid} лишние ключи {sorted(bad)} — Kun отклонит файл")
                if sid == "rlm" and srv.get("timeoutMs", 30000) <= 300000:
                    fails.append(".kun/project.json: timeoutMs у rlm должен быть больше 300000")
        except ValueError as exc:
            fails.append(f".kun/project.json не JSON: {exc}")

    drift = []
    for f in sorted((p / "rules").glob("*.md")) + sorted((p / ".kun/agents").glob("*.md")):
        rel = f.relative_to(p).as_posix()
        srcs = [s for s in install_sources(rel) if (b / s).is_file()]
        if srcs and digest(f) != digest(b / srcs[0]):
            drift.append(rel)
    if drift:
        notes.append(f"отличаются от текущей сборки (правки проекта или старая версия): {', '.join(drift)}")

    print(f"Проверка проекта {p} против сборки {b}")
    for f in fails:
        print(f"- FAIL  {f}")
    for n in notes:
        print(f"- info  {n}")
    print("OK: проект собран" if not fails else f"\nпроблем: {len(fails)}")
    return {"fails": fails, "notes": notes}, (1 if fails else 0)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="развести сборку BR-deepseek и 1С-проект")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("inventory")
    a.add_argument("x")
    c = sub.add_parser("carry")
    c.add_argument("x")
    c.add_argument("p")
    c.add_argument("--apply", action="store_true")
    g = c.add_mutually_exclusive_group()
    g.add_argument("--with-build-edits", action="store_true")
    g.add_argument("--skip-build-edits", action="store_true")
    c.add_argument("--include", action="append", default=[], metavar="ПУТЬ")
    v = sub.add_parser("verify")
    v.add_argument("p")
    v.add_argument("b")
    for s in (a, c, v):
        s.add_argument("--out", metavar="ОТЧЁТ.json")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "inventory":
            report = inventory(Path(args.x))
            code = print_inventory(report)
        elif args.cmd == "carry":
            report, code = carry(Path(args.x), Path(args.p), args)
        else:
            report, code = verify(Path(args.p), Path(args.b))
    except InputError as exc:
        sys.stderr.write(f"ошибка: {exc}\n")
        return 2
    if args.out:
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nотчёт: {args.out}")
    return code


if __name__ == "__main__":
    sys.exit(main())
