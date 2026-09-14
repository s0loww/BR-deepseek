"""Minimal BSL scanner: just enough structure for rule checks.

Not a parser. It answers four questions a regex cannot answer on its own:

  * where do comments and string literals sit, so a pattern does not fire on a
    word inside a message or a commented-out line;
  * which procedure a line belongs to, and what annotations that procedure
    carries (`&Вместо`, `&Перед`, ...);
  * whether a line sits inside a loop;
  * what the positional arguments of a call are, with nesting respected.

Standard library only, no external dependencies: this tool travels with the
rules, and the two must stay independently installable.
"""
import re

SPACE = " "

_PROC_START = re.compile(
    r"^[ \t]*(?P<kw>Процедура|Функция|Procedure|Function)[ \t]+"
    r"(?P<name>[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё_0-9]*)", re.IGNORECASE)
_PROC_END = re.compile(r"^[ \t]*(?:КонецПроцедуры|КонецФункции|EndProcedure|EndFunction)\b",
                       re.IGNORECASE)
_ANNOTATION = re.compile(r"^[ \t]*&(?P<name>[A-Za-zА-Яа-яЁё_]+)"
                         r"(?:\([ \t]*\"(?P<target>[^\"]*)\"[ \t]*\))?", re.IGNORECASE)
_LOOP_START = re.compile(r"(?:^|[ \t;])(?:Цикл|Do)[ \t]*(?://.*)?$", re.IGNORECASE)
_LOOP_END = re.compile(r"^[ \t]*(?:КонецЦикла|EndDo)\b", re.IGNORECASE)


def read_source(path):
    """1C exports are UTF-8 with BOM, sometimes UTF-16 or cp1251."""
    raw = open(path, "rb").read()
    for encoding in ("utf-8-sig", "utf-16", "cp1251"):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return raw.decode("utf-8", "replace")


def blank_noise(text):
    """Replace comment and string-literal contents with spaces, in place.

    Offsets and line numbers are preserved, so a match position in the blanked
    text points at the same place in the original. That is what lets a rule
    match on structure while quoting the real line back to the user.

    BSL strings close on a lone `"`; a doubled `""` is an escaped quote, and a
    literal may span lines with `|` continuations.
    """
    out = list(text)
    index = 0
    length = len(text)
    in_string = False
    while index < length:
        char = text[index]
        if in_string:
            if char == '"':
                if index + 1 < length and text[index + 1] == '"':
                    out[index] = out[index + 1] = SPACE
                    index += 2
                    continue
                in_string = False
                index += 1
                continue
            if char != "\n":
                out[index] = SPACE
            index += 1
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "/":
            while index < length and text[index] != "\n":
                out[index] = SPACE
                index += 1
            continue
        index += 1
    return "".join(out)


class Procedure(object):
    __slots__ = ("name", "kind", "start", "end", "annotations", "targets")

    def __init__(self, name, kind, start, end, annotations, targets):
        self.name = name
        self.kind = kind                  # procedure | function
        self.start = start                # 1-based line of the declaration
        self.end = end                    # 1-based line of the closing keyword
        self.annotations = annotations    # lower-cased, e.g. {"вместо"}
        self.targets = targets            # intercepted method names

    def contains(self, line):
        return self.start <= line <= self.end

    def has(self, *names):
        return any(name.lower() in self.annotations for name in names)


def procedures(blanked, original=None):
    """Every routine with the annotations attached to it.

    Structure is read from the blanked text so a keyword inside a comment
    cannot open a routine; the intercepted method name is read back from the
    original, because in the blanked text it is a run of spaces. That split --
    decide on blanked, display from original -- holds throughout this module.
    """
    lines = blanked.split(chr(10))
    original_lines = original.split(chr(10)) if original is not None else lines
    found = []
    pending_annotations = []
    pending_targets = []
    current = None
    for number, line in enumerate(lines, 1):
        annotation = _ANNOTATION.match(line)
        if annotation and current is None:
            pending_annotations.append(annotation.group("name").lower())
            if annotation.group("target") is not None:
                source_line = (original_lines[number - 1]
                               if number <= len(original_lines) else line)
                real = _ANNOTATION.match(source_line)
                pending_targets.append(
                    (real.group("target") if real and real.group("target")
                     else annotation.group("target")).strip())
            continue
        start = _PROC_START.match(line)
        if start and current is None:
            current = Procedure(
                name=start.group("name"),
                kind="function" if start.group("kw").lower() in ("функция", "function")
                else "procedure",
                start=number, end=number,
                annotations=set(pending_annotations), targets=list(pending_targets))
            pending_annotations, pending_targets = [], []
            continue
        if current is not None and _PROC_END.match(line):
            current.end = number
            found.append(current)
            current = None
            continue
        if current is None and line.strip():
            pending_annotations, pending_targets = [], []
    if current is not None:               # unterminated routine: keep what we saw
        current.end = len(lines)
        found.append(current)
    return found


def procedure_at(routines, line):
    for routine in routines:
        if routine.contains(line):
            return routine
    return None


def loop_lines(blanked):
    """Line numbers that sit strictly inside a loop body."""
    inside = set()
    depth = 0
    for number, line in enumerate(blanked.split(chr(10)), 1):
        if _LOOP_END.match(line):
            depth = max(0, depth - 1)
            continue
        if depth:
            inside.add(number)
        if _LOOP_START.search(line):
            depth += 1
    return inside


def split_args(argument_text):
    """Split a call's argument list on top-level commas.

    Omitted positional arguments are legal in BSL (`Ф(А, , Б)`) and carry
    meaning, so empty slots are preserved rather than dropped.
    """
    args = []
    depth = 0
    current = []
    for char in argument_text:
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        if char == "," and depth == 0:
            args.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    args.append("".join(current).strip())
    if len(args) == 1 and not args[0]:
        return []
    return args


def calls(blanked, name, original=None):
    """Every call of `name`, as (line, args, raw_args).

    `args` come from the blanked text: a string literal reads as blanks there,
    which is exactly what the positional-slot rules need -- a literal must not
    pass for an enum reference just because it spells one. `raw_args` are the
    same slots sliced from the original, for quoting back to the reader.
    """
    pattern = re.compile(r"(?<![A-Za-zА-Яа-яЁё_0-9.])" + re.escape(name) + r"[ \t]*\(")
    out = []
    for match in pattern.finditer(blanked):
        open_paren = match.end() - 1
        depth = 0
        index = open_paren
        while index < len(blanked):
            char = blanked[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    break
            index += 1
        else:
            continue                       # unbalanced: skip rather than guess
        line = blanked.count("\n", 0, match.start()) + 1
        args = split_args(blanked[open_paren + 1:index])
        raw = (split_args(original[open_paren + 1:index])
               if original is not None else args)
        out.append((line, args, raw))
    return out


def find_lines(blanked, pattern):
    """Line numbers where a compiled pattern matches the blanked text."""
    return [number for number, line in enumerate(blanked.split(chr(10)), 1)
            if pattern.search(line)]
