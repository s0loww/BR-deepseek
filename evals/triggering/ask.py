#!/usr/bin/env python3
"""Прогон задания триггеринга через DeepSeek API.

Зачем отдельный ранер. В airules на задание отвечает агент сессии — там это
честно, потому что сессия и есть целевая среда. Здесь целевая модель другая,
чем та, что ведёт разработку, поэтому её надо звать явно.

Почему напрямую в API, а не через `kun run`. Kun хранит ключ в собственном
зашифрованном credentials-store, привязанном к его data-dir, и ключ из
конфига не подхватывает; поднимать ради текстового замера второй профиль
среды — возня без выигрыша. Задание не использует инструменты, так что от
среды здесь зависит только системный промпт, а он не предмет замера.

    python evals/triggering/ask.py answers-1.json          # один прогон
    python evals/triggering/ask.py answers.json --runs 3   # answers-1..3.json
    python evals/triggering/ask.py a.json --effort high    # ступень усилия
    python evals/triggering/ask.py a.json --overlay 1c     # ядро + 1С-оверлей

Про лимит вывода. deepseek-v4-pro — reasoning-модель: рассуждение тратит тот
же бюджет `max_tokens`, что и ответ. На 4096 весь бюджет уходит в
`reasoning_content`, `content` приходит пустым, а `finish_reason` — `length`.
Отсюда дефолт в 16384 и явная диагностика этого случая. Рассуждение растёт с
числом кейсов: на 60 кейсах ядра с 1С-оверлеем при `high` 16384 не хватило
(64 тыс. символов рассуждения) — для него `--max-tokens 32768`.

Ключ: переменная DEEPSEEK_API_KEY или файл `.env` в корне сборки (одна
строка с ключом). Чистая стандартная библиотека.
"""

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
API = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-v4-pro"
MAX_TOKENS = 16384
OVERLAY_ARGS = []  # ["--overlay", "1c"] — промпт по ядру + оверлею, см. run.py


def read_key():
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    env_path = os.path.join(REPO, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8-sig") as handle:
            raw = handle.read().strip()
        # допускаем и голый ключ, и строку KEY=значение
        return raw.split("=", 1)[1].strip() if "=" in raw else raw
    sys.stderr.write("нет ключа: задай DEEPSEEK_API_KEY или положи .env в корень\n")
    sys.exit(2)


def build_prompt():
    """Промпт строится тем же скриптом, что и для ручного прогона, — чтобы
    задание нельзя было случайно разойтись между двумя путями запуска."""
    out = subprocess.run(
        [sys.executable, os.path.join(HERE, "run.py"), "prompt"] + OVERLAY_ARGS,
        capture_output=True, check=True,
    )
    return out.stdout.decode("utf-8")


def ask(prompt, key, model, effort=None):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": MAX_TOKENS,
    }
    if effort:
        payload["reasoning_effort"] = effort
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(API, data=body, headers={
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=900) as resp:
        answer = json.load(resp)
    choice = answer["choices"][0]
    content = choice["message"].get("content") or ""
    if not content.strip():
        reason = choice.get("finish_reason")
        thought = len(choice["message"].get("reasoning_content") or "")
        raise RuntimeError(
            "модель вернула пустой ответ (finish_reason={0}, рассуждения {1} симв.) — "
            "подними MAX_TOKENS или опусти ступень усилия".format(reason, thought))
    return content, answer.get("usage", {})


def extract_json(text):
    """Ответ приходит и голым JSON, и в ```json-заборе, и с прозой вокруг."""
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidate = fence.group(1) if fence else None
    if candidate is None:
        start = text.find("{")
        end = text.rfind("}")
        candidate = text[start:end + 1] if start != -1 and end > start else None
    if candidate is None:
        raise ValueError("в ответе нет JSON-объекта")
    return json.loads(candidate)


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    out_path = argv[0]
    runs = 1
    model = DEFAULT_MODEL
    if "--runs" in argv:
        runs = int(argv[argv.index("--runs") + 1])
    if "--model" in argv:
        model = argv[argv.index("--model") + 1]
    effort = argv[argv.index("--effort") + 1] if "--effort" in argv else None
    if "--overlay" in argv:
        OVERLAY_ARGS.extend(["--overlay", argv[argv.index("--overlay") + 1]])
    if "--max-tokens" in argv:
        global MAX_TOKENS
        MAX_TOKENS = int(argv[argv.index("--max-tokens") + 1])

    key = read_key()
    prompt = build_prompt()
    base, ext = os.path.splitext(out_path)

    for n in range(1, runs + 1):
        target = out_path if runs == 1 else "{0}-{1}{2}".format(base, n, ext)
        content, usage = ask(prompt, key, model, effort)
        try:
            answers = extract_json(content)
        except ValueError as exc:
            sys.stderr.write("прогон {0}: {1}\n".format(n, exc))
            with open(target + ".raw.txt", "w", encoding="utf-8") as handle:
                handle.write(content)
            sys.stderr.write("сырой ответ сохранён в {0}.raw.txt\n".format(target))
            return 1
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(answers, handle, ensure_ascii=False, indent=2)
        print("прогон {0}: {1} ответов -> {2} (токенов: {3})".format(
            n, len(answers), target, usage.get("total_tokens", "?")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
