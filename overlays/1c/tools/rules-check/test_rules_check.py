"""Gate for the rule checker.

Two directions, and the first matters more:

  * `fixtures/clean/` must produce **nothing**. A checker that cries wolf gets
    switched off, and then the rules it did get right stop being enforced too.
    Every false positive found against a real configuration is added there, so
    it can never come back.
  * `fixtures/dirty/` must produce exactly the recorded set — the recall side,
    pinned by `fixtures/expected.json`.

    python test_rules_check.py
    python test_rules_check.py --update   # re-baseline after reviewing output
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bsl                                          # noqa: E402
from rules import RULES                             # noqa: E402
from rules_check import check_file, collect         # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures")
CLEAN = os.path.join(FIXTURES, "clean")
DIRTY = os.path.join(FIXTURES, "dirty")
EXPECTED = os.path.join(FIXTURES, "expected.json")


def scan(directory):
    found = []
    for path, _ok in [(p, True) for p in collect("path", HERE, directory)[0]]:
        for violation in check_file(path):
            record = violation.as_dict()
            record["path"] = os.path.relpath(path, FIXTURES).replace(os.sep, "/")
            found.append(record)
    found.sort(key=lambda v: (v["path"], v["line"], v["rule"]))
    return found


def checks():
    out = []

    def eq(label, got, want):
        out.append((got == want, label + ": got " + repr(got) + ", want " + repr(want)))

    def ok(label, condition, detail=""):
        out.append((bool(condition), label + (": " + detail if detail else "")))

    # -- precision: the clean corpus must stay silent -------------------
    clean = scan(CLEAN)
    eq("clean fixtures produce nothing", clean, [])

    # -- recall: every rule has a case that trips it --------------------
    dirty = scan(DIRTY)
    tripped = {v["rule"] for v in dirty}
    declared = {rule["id"] for rule in RULES}
    eq("every declared rule has a dirty case", sorted(declared - tripped), [])
    eq("no rule fires that is not declared", sorted(tripped - declared), [])

    # -- the scanner, on the properties the rules depend on -------------
    blanked = bsl.blank_noise('А = "текст с ПродолжитьВызов()"; // и #Вставка\nБ = 1;')
    ok("string contents are blanked", "ПродолжитьВызов" not in blanked, blanked[:40])
    ok("comments are blanked", "#Вставка" not in blanked)
    eq("line count survives blanking", blanked.count("\n"), 1)

    doubled = bsl.blank_noise('А = "он сказал ""да"" вчера"; Б = ПродолжитьВызов();')
    ok("a doubled quote does not end the literal", "ПродолжитьВызов" in doubled, doubled)

    eq("omitted positional slots are preserved",
       bsl.split_args('А, , Б'), ["А", "", "Б"])
    eq("nested calls do not split", bsl.split_args('Ф(А, Б), В'), ["Ф(А, Б)", "В"])
    eq("an empty argument list is empty", bsl.split_args(''), [])

    routines = bsl.procedures(bsl.blank_noise(
        '&НаСервере\n&Вместо("Тест")\n// комментарий между аннотацией и объявлением\n'
        'Процедура ДЕМО_Тест()\nКонецПроцедуры\n'
        'Процедура БезАннотаций()\nКонецПроцедуры\n'))
    eq("annotations survive a comment before the declaration",
       sorted(routines[0].annotations), ["вместо", "насервере"])
    eq("annotations do not leak to the next routine", sorted(routines[1].annotations), [])

    # -- suppression marker ---------------------------------------------
    suppressed = check_file("inline.bsl", 'Процедура П()\n'
                            '\tЗапрос.Выполнить(); // airules:allow query-in-loop\n'
                            'КонецПроцедуры\n')
    eq("the allow marker suppresses its own rule", suppressed, [])

    # -- snapshot --------------------------------------------------------
    if not os.path.exists(EXPECTED):
        out.append((False, "expected.json missing -- run with --update"))
        return out
    with io.open(EXPECTED, encoding="utf-8") as handle:
        want = json.load(handle)
    eq("dirty fixtures match the snapshot", dirty, want)
    return out


def main():
    if "--update" in sys.argv:
        with io.open(EXPECTED, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(scan(DIRTY), handle, ensure_ascii=False, indent=1, sort_keys=True)
        print("expected.json перезаписан")
        return 0
    failures = []
    for good, message in checks():
        print(("  ok   " if good else "  FAIL ") + message[:200])
        if not good:
            failures.append(message)
    print()
    print(("FAILED: " + str(len(failures))) if failures else "все проверки зелёные")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
