#!/usr/bin/env python3
"""Бенчмарк триггеринга правил: находится ли правило по формулировке задачи.

Что измеряется. Доставка правил стоит на том, что модель выберет нужное правило
по его `description` из индекса. Гейты в `ci/check_layers.py` проверяют, что
правило существует, объявило жанр и что на него ссылаются, — но ни один не
проверяет, что оно **находится**. Здесь проверяется ровно это.

Почему без модели внутри. Скрипт печатает промпт, отвечает агент в сессии,
скрипт сверяет ответы. Так не нужны ни ключи, ни провайдер, ни токены вне
сессии, и проверяется та модель, которой пользуются, а не чужая.

    python evals/triggering/run.py prompt  > prompt.md   # выдать задание
    python evals/triggering/run.py score answers.json    # сверить ответы

Отвечать должна модель целевой среды, а не сессия, которая правила эти правила.
Прогон через Kun:

    kun run --prompt-file prompt.md --model deepseek-v4-pro --reasoning-effort high

Формат `answers.json` (его же печатает промпт как шаблон):

    {"mem-report": ["dcs-composition-recipes"], "slow-query": ["anti-patterns"]}

**Условие честного прогона.** Отвечать должна сессия, в контексте которой нет
тел правил, — иначе меряется память сессии, а не описания. Практически: свежая
сессия, только индекс из промпта.

Чистая стандартная библиотека, Python 3.8+.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
RULE_DIRS = ["rules"]
DESC_RE = re.compile(r'^description:\s*"?(.*?)"?\s*$')


def load_index():
    """{stem: description} по всем правилам дистрибутива."""
    index = {}
    for rel_dir in RULE_DIRS:
        abs_dir = os.path.join(REPO, rel_dir)
        if not os.path.isdir(abs_dir):
            continue
        for name in sorted(os.listdir(abs_dir)):
            if not name.endswith(".md"):
                continue
            path = os.path.join(abs_dir, name)
            with open(path, "r", encoding="utf-8-sig") as handle:
                lines = handle.read().splitlines()
            desc = ""
            for line in lines[1:]:
                if line.strip() == "---":
                    break
                match = DESC_RE.match(line)
                if match:
                    desc = match.group(1)
            index[name[:-3]] = desc
    return index


def load_cases():
    with open(os.path.join(HERE, "cases.json"), "r", encoding="utf-8-sig") as handle:
        return json.load(handle)["cases"]


def warn_stale_cases(index, cases):
    """Кейс ссылается на правило по имени. Правило переименовали — кейс молча
    перестал что-либо проверять: ожидание не совпадёт никогда, и это выглядит
    как провал описания, а не как протухший кейс. Ловим сразу."""
    stale = set()
    for case in cases:
        for name in list(case.get("expect", [])) + list(case.get("forbid", [])):
            if name not in index:
                stale.add((case["id"], name))
    for case_id, name in sorted(stale):
        sys.stderr.write(
            "ВНИМАНИЕ: кейс {0} ссылается на несуществующее правило '{1}'\n".format(
                case_id, name
            )
        )
    return len(stale)


WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё-]{4,}")
# Слова, общие для домена и потому не свидетельствующие о списывании.
BIAS_STOP = {
    "правил", "правило", "правила", "нужно", "надо", "когда", "который",
    "которые", "которое", "загрузить", "чтобы", "после", "перед", "через",
}


def cmd_bias():
    """Проверка на списывание кейса с описания.

    Запрос должен быть написан словами человека с проблемой. Если он собран из
    отличительных слов целевого описания, кейс проверяет описание само против
    себя и всегда зелёный — самый лёгкий способ получить бессмысленные сто
    процентов. Меряем пересечение словаря запроса со словарём описания цели,
    вычтя слова, общие для всего индекса (они домена, а не списывания)."""
    index = load_index()
    cases = load_cases()

    def words(text):
        return {w.lower() for w in WORD_RE.findall(text or "")} - BIAS_STOP

    # Слово, встречающееся в описаниях многих правил, ничего не выдаёт.
    freq = {}
    for desc in index.values():
        for word in words(desc):
            freq[word] = freq.get(word, 0) + 1
    common = {w for w, n in freq.items() if n >= 4}

    print("кейс                     общих отличительных слов с описанием цели")
    flagged = 0
    for case in cases:
        query_words = words(case["query"])
        for target in case.get("expect", []):
            shared = sorted((query_words & words(index.get(target, ""))) - common)
            mark = ""
            if len(shared) >= 3:
                mark = "  <== проверить формулировку"
                flagged += 1
            print("{0:24} {1:2}  {2}{3}".format(
                case["id"], len(shared), ", ".join(shared) or "—", mark))
    print("\nпод подозрением: {0}".format(flagged))
    return 0


def cmd_prompt():
    index = load_index()
    cases = load_cases()
    warn_stale_cases(index, cases)
    out = []
    out.append("# Задание: выбор правил по описанию\n")
    out.append(
        "Ниже индекс правил (имя и описание) и список запросов. Для каждого "
        "запроса назови правила, которые ты бы прочитал, прежде чем браться. "
        "Опирайся **только** на индекс: тела правил открывать нельзя, "
        "догадываться по именам файлов вне индекса — тоже.\n"
    )
    out.append(
        "Отвечай минимально: одно-два правила на запрос. Если ни одно не "
        "подходит — пустой список, это валидный ответ и полезный сигнал.\n"
    )
    out.append("## Индекс правил\n")
    for stem in sorted(index):
        out.append("- **{0}** — {1}".format(stem, index[stem] or "(без описания)"))
    out.append("\n## Запросы\n")
    for case in cases:
        out.append("- `{0}`: {1}".format(case["id"], case["query"]))
    out.append("\n## Формат ответа\n")
    out.append("Один JSON-объект, ключ — id запроса, значение — список имён правил:\n")
    template = {case["id"]: [] for case in cases}
    out.append("```json")
    out.append(json.dumps(template, ensure_ascii=False, indent=2))
    out.append("```")
    print("\n".join(out))
    return 0


def cmd_score(answers_path):
    index = load_index()
    cases = load_cases()
    with open(answers_path, "r", encoding="utf-8-sig") as handle:
        answers = json.load(handle)
    stale = warn_stale_cases(index, cases)

    clean = 0
    unknown_names = set()
    surfaced = set()
    problems = []

    for case in cases:
        got = list(answers.get(case["id"], []))
        surfaced.update(got)
        unknown_names.update(name for name in got if name not in index)
        missed = [r for r in case.get("expect", []) if r not in got]
        banned = [r for r in case.get("forbid", []) if r in got]
        if not missed and not banned:
            clean += 1
            continue
        problems.append((case["id"], missed, banned, got))

    print("кейсов: {0}, чисто: {1}, с промахом: {2}".format(
        len(cases), clean, len(problems)))

    if problems:
        print("\n== ПРОМАХИ ==")
        for case_id, missed, banned, got in problems:
            print("  {0}".format(case_id))
            if missed:
                print("    не поднялось: {0}".format(", ".join(missed)))
            if banned:
                print("    поднялось лишнее: {0}".format(", ".join(banned)))
            print("    ответ: {0}".format(", ".join(got) if got else "(пусто)"))

    if unknown_names:
        print("\n== ИМЕНА ВНЕ ИНДЕКСА (правило переименовано или выдумано) ==")
        for name in sorted(unknown_names):
            print("  {0}".format(name))

    # Правило, не всплывшее ни в одном кейсе, — либо тема не покрыта кейсами,
    # либо описание не работает. Различает это человек, но список нужен.
    never = sorted(set(index) - surfaced)
    print("\n== НИ РАЗУ НЕ ВСПЛЫЛИ ({0} из {1}) ==".format(len(never), len(index)))
    print("  " + ", ".join(never) if never else "  —")

    return 1 if problems or unknown_names or stale else 0


def main(argv):
    # Под Windows перенаправленный stdout берёт кодировку системы (cp1251), и
    # печать промпта падает на первом же символе вне неё. Вывод у нас всегда
    # utf-8 — задаём его явно, чтобы `run.py prompt > prompt.md` работал как
    # написано в docstring, без PYTHONIOENCODING снаружи.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not argv or argv[0] not in ("prompt", "score", "bias"):
        print(__doc__)
        return 2
    if argv[0] == "bias":
        return cmd_bias()
    if argv[0] == "prompt":
        return cmd_prompt()
    if len(argv) < 2:
        print("нужен путь к answers.json")
        return 2
    return cmd_score(argv[1])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
