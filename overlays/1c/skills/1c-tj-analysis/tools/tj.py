#!/usr/bin/env python3
"""Разбор технологического журнала 1С (ТЖ): сводки для поиска долгих вызовов,
долгих запросов, ожиданий блокировок и ошибок.

Только чтение. Вход — каталог журнала, отдельный `.log`, архив `.zip` или
`.7z` (через 7z.exe). Архив читается потоком, без распаковки на диск.

    python tj.py inventory <путь>                       что журнал вообще записал
    python tj.py top <путь> --event CALL,SCALL --by context
    python tj.py top <путь> --event DBMSSQL,SDBL --by sql
    python tj.py slowest <путь> --event DBMSSQL -n 20    самые долгие одиночные события
    python tj.py locks <путь>                           ожидания, таймауты, взаимоблокировки
    python tj.py errors <путь>                          EXCP / QERR по местам кода

Общие флаги: --from ГГММДДЧЧ, --to ГГММДДЧЧ (по именам файлов, включительно),
--infobase ИМЯ (p:processName), --json, --out ФАЙЛ (.json — JSON, иначе
markdown), --7z ПУТЬ.

Приватность. Журнал содержит тексты запросов с параметрами, имена
пользователей и компьютеров, значения ключей блокировок. По умолчанию ничего
из этого не печатается: запросы группируются по отпечатку нормализованного
текста, от ошибок остаются место кода и класс исключения. `--sql` добавляет
нормализованный текст запроса (литералы, числа и параметры заменены на `?`),
`--descr` — начало описания ошибки. Места кода (Context) печатаются всегда:
это строки исходного кода конфигурации, а не данные.

Длительность. В 8.3 время события пишется с 6 знаками дроби и длительность —
в микросекундах; в 8.2 — 4 знака и десятитысячные секунды. Скрипт определяет
единицу по формату времени и всё приводит к микросекундам.

Коды выхода: 0 — сводка построена; 1 — под запрос нет событий (журнал их не
записывал или фильтры всё отсекли — смотреть inventory); 2 — ошибка входа;
3 — сводка построена, но часть файлов прочитать не удалось.

Только стандартная библиотека, Python 3.8+.
"""

import argparse
import collections
import contextlib
import hashlib
import heapq
import io
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

START = re.compile(r"^(\d{2}):(\d{2})\.(\d{4,6})-(\d+),([A-Za-z_]+),(\d+)(?=,|\r?\n|$)")
OPEN_QUOTE = re.compile(r"=(['\"])")
UNQUOTED_END = re.compile(r"[,\r\n]")
HOUR_NAME = re.compile(r"(\d{8})\.log$", re.I)

CALL_EVENTS = ("CALL", "SCALL")
QUERY_EVENTS = ("DBMSSQL", "DBPOSTGRS", "DBORACLE", "DB2", "DBV8DBENG", "SDBL")
LOCK_EVENTS = ("TLOCK", "TTIMEOUT", "TDEADLOCK")
ERROR_EVENTS = ("EXCP", "QERR")
DURATION_EVENTS = CALL_EVENTS + QUERY_EVENTS + ("TLOCK", "TTIMEOUT")
GROUPINGS = ("context", "context-first", "stack", "module", "sql", "infobase",
             "event", "hour", "process", "regions")

DEFAULT_7Z = (r"C:\Program Files\7-Zip\7z.exe", r"C:\Program Files (x86)\7-Zip\7z.exe")


class InputError(Exception):
    pass


# ---------------------------------------------------------------- источники

class Source:
    def __init__(self, label, opener):
        self.label = label
        self.opener = opener
        m = HOUR_NAME.search(label)
        self.hour = m.group(1) if m else None
        parts = re.split(r"[\\/]", label)
        self.process = parts[-2] if len(parts) >= 2 else ""


def find_7z(explicit):
    for cand in (explicit, os.environ.get("SEVENZIP"), "7z", "7za") + DEFAULT_7Z:
        if not cand:
            continue
        found = shutil.which(cand) or (cand if Path(cand).is_file() else None)
        if found:
            return found
    raise InputError("архив .7z, но 7z не найден: укажи --7z ПУТЬ или переменную SEVENZIP")


def discover(path, sevenzip=None):
    p = Path(path)
    if not p.exists():
        raise InputError(f"нет такого пути: {path}")
    if p.is_dir():
        files = sorted(f for f in p.rglob("*") if f.is_file() and f.suffix.lower() == ".log")
        return [Source(f.relative_to(p).as_posix(), lambda f=f: _file_stream(f)) for f in files]
    suffix = p.suffix.lower()
    if suffix == ".log":
        return [Source(p.parent.name + "/" + p.name, lambda: _file_stream(p))]
    if suffix == ".zip":
        with zipfile.ZipFile(p) as zf:
            names = sorted(n for n in zf.namelist() if n.lower().endswith(".log"))
        return [Source(n, lambda n=n: _zip_stream(p, n)) for n in names]
    if suffix == ".7z":
        exe = find_7z(sevenzip)
        listing = subprocess.run([exe, "l", "-slt", "-sccUTF-8", str(p)], capture_output=True)
        if listing.returncode != 0:
            raise InputError(f"7z не прочитал архив: {path}")
        text = listing.stdout.decode("utf-8", "replace")
        names = sorted(m.group(1).strip() for m in re.finditer(r"^Path = (.+\.log)\s*$", text, re.M | re.I))
        return [Source(n, lambda n=n: _7z_stream(exe, p, n)) for n in names]
    raise InputError(f"не понимаю вход: {path} (нужен каталог, .log, .zip или .7z)")


def _text(binary):
    return io.TextIOWrapper(binary, encoding="utf-8-sig", errors="replace", newline="")


@contextlib.contextmanager
def _file_stream(path):
    with open(path, "rb") as fh:
        yield _text(fh)


@contextlib.contextmanager
def _zip_stream(archive, name):
    with zipfile.ZipFile(archive) as zf, zf.open(name) as fh:
        yield _text(fh)


@contextlib.contextmanager
def _7z_stream(exe, archive, name):
    proc = subprocess.Popen([exe, "e", "-so", str(archive), name],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        yield _text(proc.stdout)
    finally:
        proc.stdout.close()
        if proc.wait() != 0:
            raise OSError(f"7z завершился с кодом {proc.returncode} на {name}")


# ---------------------------------------------------------------- разбор

def quote_state(line, quote):
    """Открытая кавычка после строки или None. Кавычка внутри значения удвоена."""
    i, n = 0, len(line)
    while True:
        if quote is None:
            m = OPEN_QUOTE.search(line, i)
            if not m:
                return None
            quote, i = m.group(1), m.end()
        k = line.find(quote, i)
        if k < 0:
            return quote
        if k + 1 < n and line[k + 1] == quote:
            i = k + 2
            continue
        quote, i = None, k + 1


def parse_props(text):
    """',ключ=значение,…' → dict. Значения в ' или " могут занимать несколько строк."""
    props = {}
    i, n = 0, len(text)
    while i < n:
        if text[i] in ",\r\n\t ":
            i += 1
            continue
        eq = text.find("=", i)
        if eq < 0:
            break
        key = text[i:eq].strip()
        j = eq + 1
        if j < n and text[j] in "'\"":
            quote, j, parts = text[j], j + 1, []
            while True:
                k = text.find(quote, j)
                if k < 0:
                    parts.append(text[j:])
                    j = n
                    break
                if k + 1 < n and text[k + 1] == quote:
                    parts.append(text[j:k + 1])
                    j = k + 2
                    continue
                parts.append(text[j:k])
                j = k + 1
                break
            value = "".join(parts)
        else:
            m = UNQUOTED_END.search(text, j)
            end = m.start() if m else n
            value, j = text[j:end], end
        props.setdefault(key, value)
        i = j
    return props


class Event:
    __slots__ = ("name", "level", "dur", "ts", "hour", "process", "props", "frac")

    def __init__(self, source, text):
        m = START.match(text)
        mm, ss, frac, dur, self.name, level = m.groups()
        self.level = int(level)
        self.frac = len(frac)
        self.dur = int(dur) * 10 ** (6 - len(frac))
        self.hour = source.hour
        self.process = source.process
        h = source.hour
        self.ts = (f"20{h[0:2]}-{h[2:4]}-{h[4:6]} {h[6:8]}:{mm}:{ss}.{frac}" if h else f"{mm}:{ss}.{frac}")
        self.props = parse_props(text[m.end():])


def iter_events(sources, args, stats):
    for src in sources:
        if src.hour and ((args.hour_from and src.hour < args.hour_from)
                         or (args.hour_to and src.hour > args.hour_to)):
            continue
        stats["files"] += 1
        try:
            with src.opener() as stream:
                block, quote = None, None
                for line in stream:
                    if quote is None and START.match(line):
                        if block is not None:
                            yield from _emit(src, block, args)
                        block = [line]
                    elif block is not None:
                        block.append(line)
                    else:
                        continue
                    quote = quote_state(line, quote)
                if block is not None:
                    yield from _emit(src, block, args)
        except (OSError, zipfile.BadZipFile) as exc:
            stats["broken"].append(f"{src.label}: {exc}")


def _emit(src, block, args):
    ev = Event(src, "".join(block))
    if args.infobase and ev.props.get("p:processName") != args.infobase:
        return
    yield ev


# ---------------------------------------------------------------- признаки

def frames(ev):
    ctx = ev.props.get("Context", "")
    return [line.strip() for line in ctx.replace("\r", "").split("\n") if line.strip()]


def module_key(ev):
    p = ev.props
    if p.get("Module") and p.get("Method") and not p["Method"].isdigit():
        return f"{p['Module']}.{p['Method']}"
    if p.get("IName") and p.get("MName"):
        return f"{p['IName']}.{p['MName']}"
    return None


LITERAL = re.compile(r"N?'(?:[^']|'')*'")
DQ_LITERAL = re.compile(r'"(?:[^"]|"")*"')
HEX = re.compile(r"\b0x[0-9A-Fa-f]+\b")
NUMBER = re.compile(r"(?<![\w.#@&])-?\d+(?:\.\d+)?(?!\w)")
TEMP_TABLE = re.compile(r"#tt\d+", re.I)
PARAM_TAIL = re.compile(r"\n\s*p_\d+\s*:.*", re.S)
SPACES = re.compile(r"\s+")


def query_text(ev):
    for key in ("Sql", "Sdbl", "Query"):
        if ev.props.get(key):
            return key, ev.props[key]
    return None, None


def normalize_query(key, text):
    s = PARAM_TAIL.sub("", text)
    s = LITERAL.sub("?", s)
    if key in ("Sdbl", "Query"):  # язык запросов 1С: строки в двойных кавычках
        s = DQ_LITERAL.sub("?", s)
    s = HEX.sub("?", s)
    s = TEMP_TABLE.sub("#tt", s)
    s = NUMBER.sub("?", s)
    return SPACES.sub(" ", s).strip()


def query_fingerprint(ev):
    key, text = query_text(ev)
    if not text:
        return None, None
    norm = normalize_query(key, text)
    return "q:" + hashlib.sha1(norm.encode("utf-8")).hexdigest()[:10], norm


def group_key(ev, by):
    f = frames(ev)
    if by == "context":
        return f[-1] if f else (module_key(ev) or "(нет Context)")
    if by == "context-first":
        return f[0] if f else (module_key(ev) or "(нет Context)")
    if by == "stack":
        return " ← ".join(reversed(f))[:600] if f else "(нет Context)"
    if by == "module":
        return module_key(ev) or (f[-1] if f else "(нет модуля)")
    if by == "sql":
        return query_fingerprint(ev)[0] or "(нет текста запроса)"
    if by == "infobase":
        return ev.props.get("p:processName") or "(нет)"
    if by == "event":
        return ev.name
    if by == "hour":
        return ev.hour or "(нет)"
    if by == "process":
        return ev.process or ev.props.get("process") or "(нет)"
    if by == "regions":
        return ev.props.get("Regions") or "(нет)"
    raise InputError(f"неизвестная группировка: {by}")


def where(ev):
    f = frames(ev)
    return f[-1] if f else (module_key(ev) or "")


def waited(ev):
    return ev.name == "TLOCK" and bool(ev.props.get("WaitConnections", "").strip())


# ---------------------------------------------------------------- агрегаты

class Agg:
    __slots__ = ("count", "total", "max", "durs", "cpu", "where", "sample")

    def __init__(self):
        self.count = self.total = self.max = self.cpu = 0
        self.durs = []
        self.where = collections.Counter()
        self.sample = None

    def add(self, ev):
        self.count += 1
        self.total += ev.dur
        self.max = max(self.max, ev.dur)
        self.durs.append(ev.dur)
        cpu = ev.props.get("CpuTime", "")
        if cpu.isdigit():
            self.cpu += int(cpu)
        w = where(ev)
        if w:
            self.where[w] += 1

    def pct(self, q):
        d = sorted(self.durs)
        return d[min(len(d) - 1, int(len(d) * q))] if d else 0


def ms(us):
    return round(us / 1000, 1)


def sec(us):
    return round(us / 1e6, 2)


def section(title, columns, rows):
    return {"title": title, "columns": columns, "rows": rows}


def new_report(command, args):
    filters = {k: v for k, v in (("from", args.hour_from), ("to", args.hour_to),
                                 ("infobase", args.infobase)) if v}
    return {"command": command, "source": str(args.path), "filters": filters,
            "sections": [], "notes": []}


def parse_events(value):
    return tuple(e.strip().upper() for e in value.split(",") if e.strip()) if value else None


# ---------------------------------------------------------------- команды

def cmd_inventory(args, events, rep):
    counts = collections.Counter()
    durs = collections.defaultdict(list)
    keys = collections.defaultdict(set)
    bases = collections.Counter()
    hours = set()
    fracs = set()
    waits = 0
    for ev in events:
        counts[ev.name] += 1
        durs[ev.name].append(ev.dur)
        keys[ev.name].update(ev.props)
        bases[ev.props.get("p:processName") or "(нет)"] += 1
        if ev.hour:
            hours.add(ev.hour)
        fracs.add(ev.frac)
        waits += waited(ev)
    if not counts:
        rep["notes"].append("Событий не найдено.")
        return 1
    unit = ", ".join({6: "микросекунды (8.3)", 4: "десятитысячные секунды (8.2)"}.get(f, f"{f} знаков") for f in sorted(fracs))
    period = f"{min(hours)} … {max(hours)}" if hours else "(имена файлов без часа)"
    rep["sections"].append(section("Журнал", ["что", "значение"], [
        ["файлов прочитано", args.stats["files"]], ["период (ГГММДДЧЧ)", period],
        ["часов с событиями", len(hours)], ["событий", sum(counts.values())],
        ["единица длительности", unit]]))
    rows = []
    for name, n in counts.most_common():
        d = sorted(durs[name])
        rows.append([name, n, ms(d[len(d) // 2]), ms(d[min(len(d) - 1, int(len(d) * .95))]), ms(d[-1])])
    rep["sections"].append(section("События", ["событие", "количество", "p50, мс", "p95, мс", "макс, мс"], rows))
    rep["sections"].append(section("Свойства событий", ["событие", "свойства"],
                                   [[name, ", ".join(sorted(keys[name]))] for name, _ in counts.most_common()]))
    rep["sections"].append(section("Информационные базы (p:processName)", ["база", "событий"],
                                   [[b, n] for b, n in bases.most_common()]))

    def has(names):
        return [e for e in names if counts.get(e)]

    calls, queries = has(CALL_EVENTS), has(QUERY_EVENTS)
    coverage = [
        ["долгие серверные вызовы", "да" if calls else "нет", ", ".join(calls) or "нет CALL / SCALL"],
        ["долгие запросы к СУБД", "да" if queries else "нет", ", ".join(queries) or "нет DBMSSQL / SDBL / …"],
        ["ожидания управляемых блокировок", "да" if waits or counts.get("TTIMEOUT") else "нет",
         f"TLOCK с ожиданием: {waits}, TTIMEOUT: {counts.get('TTIMEOUT', 0)}"],
        ["взаимоблокировки", "да" if counts.get("TDEADLOCK") else "нет", f"TDEADLOCK: {counts.get('TDEADLOCK', 0)}"],
        ["ошибки", "да" if has(ERROR_EVENTS) else "нет", ", ".join(f"{e}: {counts[e]}" for e in has(ERROR_EVENTS)) or "нет EXCP / QERR"],
    ]
    rep["sections"].append(section("На какие вопросы журнал может ответить", ["вопрос", "ответ", "основание"], coverage))
    if not calls and not queries:
        rep["notes"].append("Долгие вызовы по этому журналу не найти: в logcfg не включены ни CALL/SCALL, "
                            "ни события запросов. Рецепт настройки — docs/logcfg.md скилла.")
    if counts.get("TLOCK") and not waits:
        rep["notes"].append("TLOCK записаны, но ни одно не ждало другое соединение — это захваты, а не конфликты.")
    return 0


def cmd_top(args, events, rep):
    wanted = parse_events(args.event) or DURATION_EVENTS
    min_us = int(args.min_ms * 1000)
    groups = collections.defaultdict(Agg)
    texts = {}
    for ev in events:
        if ev.name not in wanted or ev.dur < min_us:
            continue
        key = group_key(ev, args.by)
        groups[key].add(ev)
        if args.by == "sql" and args.sql and key not in texts:
            texts[key] = query_fingerprint(ev)[1]
    if not groups:
        rep["notes"].append(f"Событий {', '.join(wanted)} под фильтры нет — смотреть inventory.")
        return 1
    order = {"total": lambda a: a.total, "max": lambda a: a.max, "count": lambda a: a.count}[args.sort]
    columns = [args.by, "событий", "всего, с", "среднее, мс", "p95, мс", "макс, мс", "CPU, с"]
    show_where = args.by not in ("context", "context-first", "stack")
    if show_where:
        columns.append("где чаще всего")
    if texts:
        columns.append("запрос (нормализован)")
    rows = []
    for key, agg in sorted(groups.items(), key=lambda kv: order(kv[1]), reverse=True)[:args.n]:
        row = [key, agg.count, sec(agg.total), ms(agg.total / agg.count), ms(agg.pct(.95)), ms(agg.max), sec(agg.cpu)]
        if show_where:
            row.append(agg.where.most_common(1)[0][0] if agg.where else "")
        if texts:
            row.append(texts.get(key, "")[:400])
        rows.append(row)
    total = sum(a.total for a in groups.values())
    rep["sections"].append(section(
        f"Топ-{args.n} по {args.sort}: {', '.join(wanted)} (групп {len(groups)}, событий "
        f"{sum(a.count for a in groups.values())}, всего {sec(total)} с)", columns, rows))
    return 0


def cmd_slowest(args, events, rep):
    wanted = parse_events(args.event) or DURATION_EVENTS
    heap, seq = [], 0
    for ev in events:
        if ev.name not in wanted:
            continue
        seq += 1
        item = (ev.dur, seq, ev)
        if len(heap) < args.n:
            heapq.heappush(heap, item)
        elif ev.dur > heap[0][0]:
            heapq.heapreplace(heap, item)
    if not heap:
        rep["notes"].append(f"Событий {', '.join(wanted)} нет — смотреть inventory.")
        return 1
    columns = ["время", "событие", "база", "длительность, мс", "где", "запрос"]
    rows = []
    for dur, _, ev in sorted(heap, reverse=True):
        fp, norm = query_fingerprint(ev)
        q = (f"{fp} {norm[:400]}" if args.sql else fp) if fp else ""
        rows.append([ev.ts, ev.name, ev.props.get("p:processName", ""), ms(dur), where(ev), q])
    rep["sections"].append(section(f"Самые долгие события: {', '.join(wanted)}", columns, rows))
    return 0


REGION = re.compile(r"\b[A-Za-z]+\d*\.[A-Z]+\b")


def cmd_locks(args, events, rep):
    tlock = waits_n = waits_total = waits_max = 0
    by_where = collections.defaultdict(Agg)
    by_region = collections.defaultdict(Agg)
    by_hour = collections.defaultdict(Agg)
    timeouts, deadlocks = [], []
    for ev in events:
        if ev.name == "TLOCK":
            tlock += 1
            if waited(ev):
                waits_n += 1
                waits_total += ev.dur
                waits_max = max(waits_max, ev.dur)
                by_where[where(ev) or "(нет Context)"].add(ev)
                by_region[ev.props.get("Regions") or "(нет)"].add(ev)
                by_hour[ev.hour or "(нет)"].add(ev)
        elif ev.name == "TTIMEOUT":
            timeouts.append([ev.ts, ev.props.get("p:processName", ""), ev.props.get("Regions", ""), where(ev)])
        elif ev.name == "TDEADLOCK":
            regions = sorted(set(REGION.findall(ev.props.get("DeadlockConnectionIntersections", ""))))
            deadlocks.append([ev.ts, ev.props.get("p:processName", ""), ", ".join(regions), where(ev)])
    if not (tlock or timeouts or deadlocks):
        rep["notes"].append("Событий блокировок (TLOCK / TTIMEOUT / TDEADLOCK) нет — смотреть inventory.")
        return 1
    rep["sections"].append(section("Итог", ["что", "значение"], [
        ["TLOCK всего", tlock], ["TLOCK с ожиданием другого соединения", waits_n],
        ["суммарное ожидание, с", sec(waits_total)], ["самое долгое ожидание, мс", ms(waits_max)],
        ["TTIMEOUT (таймауты ожидания)", len(timeouts)], ["TDEADLOCK (взаимоблокировки)", len(deadlocks)]]))
    cols = ["событий", "всего, с", "макс, мс"]
    for title, groups, label in (("Ожидания по месту кода", by_where, "где"),
                                 ("Ожидания по пространствам блокировок", by_region, "Regions")):
        rows = [[k, a.count, sec(a.total), ms(a.max)]
                for k, a in sorted(groups.items(), key=lambda kv: kv[1].total, reverse=True)[:args.n]]
        if rows:
            rep["sections"].append(section(title, [label] + cols, rows))
    if by_hour:
        rep["sections"].append(section("Ожидания по часам", ["час"] + cols,
                                       [[k, a.count, sec(a.total), ms(a.max)] for k, a in sorted(by_hour.items())]))
    if timeouts:
        rep["sections"].append(section("Таймауты", ["время", "база", "Regions", "где"], timeouts[:args.n]))
    if deadlocks:
        rep["sections"].append(section("Взаимоблокировки", ["время", "база", "пространства", "где"], deadlocks[:args.n]))
    if tlock and not waits_n and not timeouts and not deadlocks:
        rep["notes"].append("Все TLOCK захвачены без ожидания: конфликтов управляемых блокировок в журнале нет.")
    return 0


def cmd_errors(args, events, rep):
    groups = collections.OrderedDict()
    bare = collections.Counter()
    for ev in events:
        if ev.name not in ERROR_EVENTS:
            continue
        if not ev.props:
            bare[ev.name] += 1
        key = (ev.name, where(ev) or "(нет Context)", ev.props.get("Exception", ""))
        g = groups.setdefault(key, {"count": 0, "first": ev.ts, "descr": ev.props.get("Descr", "")})
        g["count"] += 1
    if not groups:
        rep["notes"].append("Событий EXCP / QERR нет — смотреть inventory.")
        return 1
    columns = ["событие", "где", "исключение", "количество", "первое"]
    if args.descr:
        columns.append("описание (начало)")
    rows = []
    for (name, w, exc), g in sorted(groups.items(), key=lambda kv: kv[1]["count"], reverse=True)[:args.n]:
        row = [name, w, exc, g["count"], g["first"]]
        if args.descr:
            row.append(SPACES.sub(" ", g["descr"])[:200])
        rows.append(row)
    rep["sections"].append(section("Ошибки по месту кода", columns, rows))
    for name, n in bare.items():
        rep["notes"].append(f"{name}: {n} событий записаны без свойств — только время и уровень, "
                            f"места и причины не видно. Так пишет logcfg этого журнала.")
    return 0


COMMANDS = {"inventory": cmd_inventory, "top": cmd_top, "slowest": cmd_slowest,
            "locks": cmd_locks, "errors": cmd_errors}


# ---------------------------------------------------------------- вывод

def cell(value):
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def to_markdown(rep):
    out = [f"# ТЖ: {rep['command']}", "", f"Источник: `{rep['source']}`"]
    if rep["filters"]:
        out.append("Фильтры: " + ", ".join(f"{k}={v}" for k, v in rep["filters"].items()))
    for sec_ in rep["sections"]:
        out += ["", f"## {sec_['title']}", "", "| " + " | ".join(cell(c) for c in sec_["columns"]) + " |",
                "| " + " | ".join("---" for _ in sec_["columns"]) + " |"]
        out += ["| " + " | ".join(cell(v) for v in row) + " |" for row in sec_["rows"]]
    if rep["notes"]:
        out += ["", "## Замечания", ""] + [f"- {n}" for n in rep["notes"]]
    return "\n".join(out) + "\n"


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("path")
    common.add_argument("--from", dest="hour_from", metavar="ГГММДДЧЧ")
    common.add_argument("--to", dest="hour_to", metavar="ГГММДДЧЧ")
    common.add_argument("--infobase", metavar="ИМЯ")
    common.add_argument("--json", action="store_true")
    common.add_argument("--out", metavar="ФАЙЛ")
    common.add_argument("--7z", dest="sevenzip", metavar="ПУТЬ")
    common.add_argument("-n", type=int, default=20)
    parser = argparse.ArgumentParser(description="Разбор технологического журнала 1С")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inventory", parents=[common])
    top = sub.add_parser("top", parents=[common])
    top.add_argument("--event", help="через запятую; по умолчанию все события с длительностью")
    top.add_argument("--by", choices=GROUPINGS, default="context")
    top.add_argument("--sort", choices=("total", "max", "count"), default="total")
    top.add_argument("--min-ms", type=float, default=0)
    top.add_argument("--sql", action="store_true", help="показать нормализованный текст запроса")
    slow = sub.add_parser("slowest", parents=[common])
    slow.add_argument("--event")
    slow.add_argument("--sql", action="store_true")
    sub.add_parser("locks", parents=[common])
    err = sub.add_parser("errors", parents=[common])
    err.add_argument("--descr", action="store_true", help="показать начало описания ошибки")
    return parser


def run(argv):
    args = build_parser().parse_args(argv)
    for attr in ("sql", "descr"):
        if not hasattr(args, attr):
            setattr(args, attr, False)
    rep = new_report(args.command, args)
    stats = {"files": 0, "broken": []}
    args.stats = stats
    try:
        sources = discover(args.path, args.sevenzip)
        if not sources:
            raise InputError(f"в {args.path} нет файлов .log")
        code = COMMANDS[args.command](args, iter_events(sources, args, stats), rep)
    except InputError as exc:
        return 2, None, str(exc)
    rep["files"] = stats["files"]
    for broken in stats["broken"]:
        rep["notes"].append(f"не прочитан: {broken}")
    if code == 0 and stats["broken"]:
        code = 3
    rep["exit_code"] = code
    return code, rep, None


def render(rep, as_json):
    return json.dumps(rep, ensure_ascii=False, indent=1) + "\n" if as_json else to_markdown(rep)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    argv = sys.argv[1:] if argv is None else argv
    code, rep, error = run(argv)
    if error:
        sys.stderr.write(error + "\n")
        return code
    args = build_parser().parse_args(argv)
    sys.stdout.write(render(rep, args.json))
    if args.out:
        Path(args.out).write_text(render(rep, args.out.lower().endswith(".json")), encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main())
