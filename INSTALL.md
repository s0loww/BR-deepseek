# Установка в целевой проект

Ставится руками, инсталлятора нет — комплект маленький, а половина настроек
всё равно живёт в GUI Kun, куда скрипт не дотянется.

## 1. Разложить файлы

Из корня этой сборки в корень целевого проекта:

| Отсюда | Туда |
| --- | --- |
| `templates/AGENTS.md` | `AGENTS.md` |
| `rules/*.md` | `rules/` |
| `agents/roles/*.md` | `.kun/agents/` |
| `skills/*` | `.kun/skills/` |

`CLAUDE.md` не создаём: Kun читает `AGENTS.md` напрямую.

PowerShell:

```powershell
$src = '<путь к этой сборке>'; $dst = '<путь к проекту>'
New-Item -ItemType Directory -Force "$dst\rules","$dst\.kun\agents","$dst\.kun\skills" | Out-Null
Copy-Item "$src\templates\AGENTS.md" "$dst\AGENTS.md"
Copy-Item "$src\rules\*.md" "$dst\rules\"
Copy-Item "$src\agents\roles\*.md" "$dst\.kun\agents\"
Copy-Item "$src\skills\*" "$dst\.kun\skills\" -Recurse
```

## 2. Заполнить контракт

В `AGENTS.md` заменить плейсхолдеры — незаполненных остаться не должно:

- `{{PROJECT_NAME}}` — имя проекта;
- `{{LANGUAGE}}` — язык ответов (например, «русский»);
- `{{STACK}}` — стек;
- `{{SOURCE_OF_TRUTH}}` — что финально авторитетно (обычно рабочая копия);
- `{{PRIMARY_CODE_DIR}}` — корень исходников;
- `{{TEST_COMMAND}}` — команда прогона тестов, или `—`, если их нет.

Проверка: `grep -r '{{' AGENTS.md` должен молчать.

## 3. Настроить Kun

В приложении:

1. **Settings → Agents → «AGENTS.md instructions»** — включить, иначе
   контракт не подхватится. Это единственный обязательный переключатель.
2. **Settings → Agents → Skills** — убедиться, что `.kun/skills` в корнях
   сканирования (по умолчанию да).
3. **Settings → Agents** — модель сессии и усилие. Рекомендация базы:
   модель `deepseek-v4-pro`, усилие `high`; `max` — вручную под планирование
   и тяжёлые баги.
4. **Per-agent overrides** — для `explorer`, `error-fixer` и `tester`
   выставить `deepseek-v4-flash`. Из файла роли модель не подхватывается:
   см. `docs/kun-contract.md`.
5. **Approval policy и sandbox** — для новичка начинать с аппрувов и
   `workspace-write`, а не с `auto` + `danger-full-access`. Полный доступ
   без подтверждений даёт агенту право на любое действие на машине.

## 4. Проверить, что всё село

- Роли видны в панели субагентов, с подписью, что редактируются в
  `.kun/agents/*.md`, и правильной пометкой read-only у `explorer` и
  `code-reviewer`.
- Скиллы видны в списке скиллов (`powershell-windows`, `mermaid-diagrams`).
- Модель на новую сессию спросить: «какие правила у тебя загружены и откуда»
  — должен назвать контракт и индекс правил, а не пересказать содержимое
  всех восьми файлов. Если он вывалил тела правил — значит их кто-то
  подгружает всегда, и ленивая загрузка сломана.
- Задать задачу на пару файлов и посмотреть, читает ли он `rules/` по
  ситуации.

## 5. Чего в базе нет

MCP (`.kun/project.json`), хуки, слэш-команды. Что это меняет и как
добавлять — `install/layout.md` и `docs/kun-contract.md`.
