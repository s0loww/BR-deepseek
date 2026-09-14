"""The rule registry.

Every rule here restates something the overlay already says in prose, and every
one is mechanically decidable -- no heuristics, no "probably". Rules that need
navigation (is this already in БСП?) or judgement (is this handler thin?) are
deliberately absent: a checker that cries wolf gets switched off, and then the
rules it did get right stop being enforced too.

Each rule carries `source`, the rule file it comes from. When the two disagree
the prose wins and the check is wrong.
"""
import re

import bsl

ERROR = "error"
WARNING = "warning"

# --- extension interceptors (rules/extension-patterns.md) -------------------

INTERCEPTORS = ("вместо", "перед", "после")
_MARKERS = re.compile(r"#(?:Вставка|КонецВставки|Удаление|КонецУдаления)\b", re.IGNORECASE)


def check_continue_outside_instead(ctx):
    """`ПродолжитьВызов()` compiles only inside `&Вместо`."""
    for line, _args, _raw in bsl.calls(ctx.blanked, "ПродолжитьВызов"):
        routine = bsl.procedure_at(ctx.routines, line)
        if routine is None or routine.has("вместо"):
            continue
        if routine.has("перед", "после"):
            yield line, ("ПродолжитьВызов() в %s: компилируется только внутри "
                         "&Вместо" % _annotation_of(routine))
        else:
            yield line, "ПродолжитьВызов() вне &Вместо: компилируется только там"


def check_instead_without_continue(ctx):
    """A `&Вместо` that never calls the original silently drops it."""
    continued = {line for line, _args, _raw in bsl.calls(ctx.blanked, "ПродолжитьВызов")}
    for routine in ctx.routines:
        if not routine.has("вместо"):
            continue
        if any(routine.contains(line) for line in continued):
            continue
        yield routine.start, ("&Вместо(\"%s\") без ПродолжитьВызов(): оригинал не "
                              "выполнится — если замена полная, это надо указать явно"
                              % (routine.targets[0] if routine.targets else routine.name))


def check_designer_markers(ctx):
    """`#Вставка` / `#Удаление` belong to ИзменениеИКонтроль, nowhere else."""
    for line in bsl.find_lines(ctx.blanked, _MARKERS):
        routine = bsl.procedure_at(ctx.routines, line)
        if routine is None or not routine.has(*INTERCEPTORS):
            continue
        yield line, ("маркер #Вставка/#Удаление внутри %s: платформа молча "
                     "перестаёт применять модуль, деплой при этом проходит"
                     % _annotation_of(routine))


# --- event log (rules/logging-strategy.md) ---------------------------------

LOG_CALL = "ЗаписьЖурналаРегистрации"
_NUMBER = re.compile(r"^-?\d+(?:[.,]\d+)?$")
_CONSTRUCTOR = re.compile(r"^(?:Новый|New)\b", re.IGNORECASE)


def _provably_wrong(arg, enum):
    """Can we *prove* this slot holds the wrong kind of value?

    Only three shapes prove it: a string literal, a number, and a `Новый ...`
    construction. A bare identifier, a property chain or a ternary cannot be
    judged from source alone -- `ПараметрыЗаписи.РежимТранзакции` and
    `?(Успех, Уровень.Информация, Уровень.Ошибка)` are both correct and both
    unrecognisable to a pattern. Demanding proof of *correctness* instead
    flagged them, which is how a checker earns its way out of the build.
    """
    text = arg.strip()
    if not text or enum.lower() in text.lower():
        return False
    if text.startswith('"'):
        return "строковый литерал"
    if _NUMBER.match(text):
        return "число"
    if _CONSTRUCTOR.match(text):
        return "конструктор Новый"
    return False


def check_log_level_slot(ctx):
    """Slot 2 is `Уровень`; a literal there is a runtime type error."""
    for line, args, raw in bsl.calls(ctx.blanked, LOG_CALL, ctx.text):
        if len(args) < 2:
            continue
        why = _provably_wrong(args[1], "УровеньЖурналаРегистрации")
        if why:
            yield line, ("2-й аргумент %s — Уровень, а передан %s: %s"
                         % (LOG_CALL, why, _short(raw[1])))


def check_log_transaction_slot(ctx):
    """Slot 6 is `РежимТранзакции`.

    Putting the `Структура` here is the documented pitfall: it raises a type
    error at the log-write call site, and inside an `Исключение` handler that
    replaces the original error and kills the run. Only a literal structure is
    provable from source -- a variable holding one is not, and is left alone.
    """
    for line, args, raw in bsl.calls(ctx.blanked, LOG_CALL, ctx.text):
        if len(args) < 6:
            continue
        why = _provably_wrong(args[5], "РежимТранзакцииЗаписиЖурналаРегистрации")
        if why:
            yield line, ("6-й аргумент %s — РежимТранзакции, а передан %s: %s; "
                         "Структура идёт 4-м" % (LOG_CALL, why, _short(raw[5])))


# --- form modules (rules/form-reserved-names.md) ----------------------------

RESERVED_FORM_NAMES = (
    "ПараметрыВыбора", "СвязиПараметровВыбора", "СписокВыбора",
    "ПараметрыОтбора", "ОтборСтрок",
)
_RESERVED_ASSIGN = re.compile(
    r"^[ \t]*(?P<name>" + "|".join(RESERVED_FORM_NAMES) + r")[ \t]*=(?!=)")


def check_reserved_form_names(ctx):
    """A local variable named after a form-element property is captured by it."""
    if not ctx.is_form_module:
        return
    for number, line in enumerate(ctx.blanked.split(chr(10)), 1):
        match = _RESERVED_ASSIGN.match(line)
        if match:
            yield number, ("%s как локальная переменная в модуле формы: платформа "
                           "может понять это как присваивание свойству элемента"
                           % match.group("name"))


# --- queries (rules/anti-patterns.md) ---------------------------------------

_QUERY_EXEC = re.compile(r"\.\s*(?:Выполнить|Execute)\s*\(", re.IGNORECASE)


def check_query_in_loop(ctx):
    """A query executed per iteration is O(n) round trips."""
    inside = bsl.loop_lines(ctx.blanked)
    for number, line in enumerate(ctx.blanked.split(chr(10)), 1):
        if number in inside and _QUERY_EXEC.search(line):
            yield number, ("запрос выполняется в цикле: O(n) обращений к СУБД — "
                           "вынести в один запрос с параметром-списком")


RULES = (
    {"id": "ext-continue-outside-instead", "severity": ERROR,
     "check": check_continue_outside_instead,
     "source": "rules/extension-patterns.md"},
    {"id": "ext-instead-without-continue", "severity": WARNING,
     "check": check_instead_without_continue,
     "source": "rules/extension-patterns.md"},
    {"id": "ext-designer-markers", "severity": ERROR,
     "check": check_designer_markers,
     "source": "rules/extension-patterns.md"},
    {"id": "log-level-slot", "severity": ERROR,
     "check": check_log_level_slot,
     "source": "rules/logging-strategy.md"},
    {"id": "log-transaction-slot", "severity": ERROR,
     "check": check_log_transaction_slot,
     "source": "rules/logging-strategy.md"},
    {"id": "form-reserved-name", "severity": ERROR,
     "check": check_reserved_form_names,
     "source": "rules/form-reserved-names.md"},
    {"id": "query-in-loop", "severity": ERROR,
     "check": check_query_in_loop,
     "source": "rules/anti-patterns.md"},
)


def _annotation_of(routine):
    for name in INTERCEPTORS:
        if routine.has(name):
            return "&" + name.capitalize()
    return "процедуре без перехватчика"


def _short(text, limit=40):
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1] + "…"
