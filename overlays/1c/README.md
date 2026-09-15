# Оверлей 1С

Слой стека 1С поверх базы: правила разработки на платформе, 1С-версии ролей,
скиллы работы с метаданными и деплоем, инструменты и подключение
**rlm-tools-bsl (RLM)** — MCP-сервера навигации по коду и метаданным
конфигурации. Перенесён из airules с адаптацией под Kun.

## Состав

```
templates/AGENTS.1c.md     фрагмент контракта (источник)
templates/AGENTS.md        собранный контракт для 1С-проекта: python ci/assemble.py
templates/project.json     .kun/project.json — RLM как служба по HTTP
templates/project.stdio.json   то же, RLM запускается процессом Kun
rules/                     31 правило, индекс — в собранном контракте
agents/ROLES.md            реестр 1С-ролей: модели, усилия, запреты инструментов
agents/roles/              13 ролей (7 заменяют базовые, 6 добавлены)
skills/1c-metadata-manage  объекты, формы, СКД, макеты, роли, расширения, базы
skills/1c-deploy-and-test  деплой на тестовую базу и проверка после деплоя
skills/1c-tj-analysis      разбор технологического журнала + рецепт logcfg.xml
skills/img-grid-analysis   сетка пропорций по картинке для макетов
tools/agent-1c             bootstrap / doctor / analyze (BSL LS) / deploy / test
tools/com-tools            COM-автоматизация 1С из PowerShell
tools/rules-check          механическая проверка BSL по правилам оверлея
evals/cases.json           кейсы замера триггеринга 1С-правил
dev.env.example            параметры кодогенерации (префикс, комментарии)
```

## Установка в проект

Проект — отдельная папка, не клон сборки: иначе проверки сборки краснеют, а
обновления до проекта не доходят. Уже поставили в клон — разводится по
`install/split-layout.md`.

Из корня сборки в корень проекта. Порядок важен: 1С-роли копируются **после**
базовых и перезаписывают одноимённые.

| Отсюда | Туда |
| --- | --- |
| `overlays/1c/templates/AGENTS.md` | `AGENTS.md` (вместо базового шаблона) |
| `rules/*.md`, затем `overlays/1c/rules/*.md` | `rules/` |
| `agents/roles/*.md`, затем `overlays/1c/agents/roles/*.md` | `.kun/agents/` |
| `skills/*`, `overlays/1c/skills/*` | `.kun/skills/` |
| `overlays/1c/tools/*` | `tools/` |
| `overlays/1c/templates/project.json` | `.kun/project.json` |
| `overlays/1c/dev.env.example` | `.dev.env.example` |

```powershell
$src = '<путь к этой сборке>'; $dst = '<путь к проекту>'
New-Item -ItemType Directory -Force "$dst\rules","$dst\.kun\agents","$dst\.kun\skills","$dst\tools" | Out-Null
Copy-Item "$src\overlays\1c\templates\AGENTS.md" "$dst\AGENTS.md"
Copy-Item "$src\rules\*.md", "$src\overlays\1c\rules\*.md" "$dst\rules\"
Copy-Item "$src\agents\roles\*.md" "$dst\.kun\agents\"
Copy-Item "$src\overlays\1c\agents\roles\*.md" "$dst\.kun\agents\" -Force
Copy-Item "$src\skills\*", "$src\overlays\1c\skills\*" "$dst\.kun\skills\" -Recurse
Copy-Item "$src\overlays\1c\tools\*" "$dst\tools\" -Recurse
Copy-Item "$src\overlays\1c\templates\project.json" "$dst\.kun\project.json"
Copy-Item "$src\overlays\1c\dev.env.example" "$dst\.dev.env.example"
```

Рабочие файлы с кредами — `.dev.env` и профиль `tools/agent-1c` — в
`.gitignore` проекта.

### Плейсхолдеры контракта

Базовые — в `INSTALL.md`, шаг 2. Оверлей добавляет:

- `{{ONEC_SOURCE_LAYOUT}}` — раскладка исходников: «выгрузка Конфигуратора
  в XML» или «v8unpack»;
- `{{ONEC_TARGET}}` — что правим: «основная конфигурация» или «расширение
  `<Имя>`»;
- `{{RLM_PROJECT}}` — имя проекта в реестре RLM (см. ниже);
- `{{STATIC_CHECK}}` — статическая проверка: команда `tools/agent-1c`
  analyze, если BSL Language Server настроен, иначе `—`.

Проверка: `grep -r '{{' AGENTS.md` молчит, а раскладка целиком —
`python install/kun_split.py verify <проект> <сборка>` из корня сборки
(`OK: проект собран`; прогонять и после каждого обновления сборки).

## RLM: подключение

rlm-tools-bsl — открытый MCP-сервер ([Dach-Coin/rlm-tools-bsl](https://github.com/Dach-Coin/rlm-tools-bsl),
MIT). Держит SQLite-индекс конфигурации: модули, методы, граф вызовов,
метаданные, формы, расширения. Агент открывает сессию, пишет короткий Python
над хелперами индекса, и в контекст попадает только напечатанное — поиск
стоит сотни токенов, а не чтение файлов. Шесть инструментов, ~14 КБ схем в
каждой сессии.

**1. Поставить сервер** (Python 3.10+, [uv](https://docs.astral.sh/uv/)):

```powershell
uv tool install "rlm-tools-bsl[service]"
```

**2. Выбрать способ запуска** — от этого зависит, какой шаблон класть в
`.kun/project.json`:

- **служба** (`project.json`) — один процесс на машину, индекс общий для всех
  проектов:

  ```powershell
  rlm-tools-bsl service install      # 127.0.0.1:9000 по умолчанию
  rlm-tools-bsl service status
  ```

- **процесс Kun** (`project.stdio.json`, переименовать в `project.json`) —
  Kun запускает `rlm-tools-bsl --transport stdio` на сессию; ничего не
  висит в фоне, но каждый старт сессии — подъём сервера.

**3. Построить индекс** из командной строки — без агента и без пароля:

```powershell
rlm-bsl-index index build "<корень выгрузки конфигурации>"
rlm-bsl-index index info  "<корень выгрузки конфигурации>"
```

**4. Зарегистрировать проект** под именем из `{{RLM_PROJECT}}`. Реестр
меняется только инструментом `rlm_projects(action="add")` с паролем —
попросить агента в сессии Kun. **Пароль при этом проходит через модель и
уходит провайдеру**: заведите для RLM отдельный пароль, нигде больше не
используемый. Он защищает реестр и индекс от случайных изменений агентом, а
не охраняет ценный секрет.

**5. Одобрить в Kun**: Settings → Agents → Project MCP & Skills → одобрить
`.kun/project.json`. Любая правка файла снимает одобрение — Kun привязывает его
к SHA-256 файла.

**6. Держать индекс свежим.** Планировщика у RLM нет — индекс протухает с
каждым коммитом. После заметных изменений:

```powershell
rlm-bsl-index index update "<корень выгрузки конфигурации>"
```

Правило `tooling-playbooks` учит агента не верить отрицательному ответу
(«вызовов нет») на свежем коде и сообщать о протухшем индексе, а не
обновлять его самому.

### Почему `timeoutMs: 330000`

У MCP-сервера проекта Kun по умолчанию обрывает вызов через 30 секунд, а
`rlm_execute` сам ограничивает выполнение 45 секундами по умолчанию и до 300 по
максимуму. С дефолтом Kun долгий поиск по большой конфигурации обрывался бы
раньше, чем RLM успеет ответить. `ci/check.py` не даст опустить значение ниже
максимума RLM.

### Почему ни одна 1С-роль не `readOnly`

В Kun `readOnly` — это «read / grep / find / ls, без MCP и без скиллов».
Разведчик с `readOnly` не увидел бы RLM. Роли, которым нельзя править,
получают `inherit` и запрет встроенных `edit` / `write` / `bash` —
подробности в `agents/ROLES.md`.

### Какие данные куда уходят

- Всё, что печатает RLM, попадает в контекст модели и уходит провайдеру
  модели — как любое чтение файла.
- У RLM есть хелперы `llm_query`: они зовут LLM-провайдера, настроенного на
  самом сервере (`RLM_LLM_*` или `ANTHROPIC_API_KEY` в его окружении). Без
  этих переменных хелперы не работают; с ними это второй канал наружу.
- Технологический журнал содержит тексты SQL с параметрами и имена
  пользователей. Прежде чем отдавать его агенту, решите, что из этого можно
  отправлять провайдеру модели.

## Софт

| Инструмент | Зачем | Где взять |
| --- | --- | --- |
| rlm-tools-bsl | MCP навигации по коду 1С | <https://github.com/Dach-Coin/rlm-tools-bsl> |
| uv | установка rlm-tools-bsl | <https://docs.astral.sh/uv/> |
| Платформа 1С:Предприятие 8.3 | Конфигуратор, загрузка и выгрузка | <https://releases.1c.ru> (по лицензии) |
| BSL Language Server | статическая проверка (`agent-1c analyze`) | <https://github.com/1c-syntax/bsl-language-server/releases> |
| OneScript | рантайм для vanessa-runner | <https://oscript.io> |
| vanessa-runner | запуск сценарных тестов | <https://github.com/oscript-library/vanessa-runner> |
| Vanessa Automation | BDD-сценарии | <https://github.com/Pr-Mex/vanessa-automation/releases> |
| Python 3 + Pillow | скилл `img-grid-analysis` | <https://www.python.org/downloads/> |

Точные версии для тест-контура — `tools/agent-1c/toolchain.lock.json`,
порядок развёртывания — `tools/agent-1c/DEPLOYMENT.md`.

## Что из airules не перенесено

- **Хук напоминания правил** (`rule-inject` + карта путь → правило). В Kun
  хуки только машинно-глобальные; инварианты доставляются индексом
  контракта (жанр invariant — «прочитать до первой строки»).
- **Фильтры rtk** — rtk встраивается хуком Claude Code.
- **Остальные MCP 1С** (метаданные, граф, шаблоны, документация платформы,
  ИТС, проверка кода): в этой сборке один MCP — RLM. Документации платформы
  и ИТС в инструментах нет, и правила требуют помечать утверждения о
  платформе без источника как непроверенные.
- **Слэш-команда `/deploy-and-test`** — стала скиллом `1c-deploy-and-test`.

## Известное

- `tools/rules-check/test_rules_check.py`: два теста падают — так же, как в
  upstream; перенос их не трогал.
- Маркер подавления в `rules-check` и `agent-1c` называется `airules:allow` —
  историческое имя, менять его — согласованная правка кода и фикстур.
- Шесть добавленных ролей на DeepSeek не проверялись. Если цепочка ролей не
  держится, работа остаётся у оркестратора, а роль можно убрать из
  `.kun/agents/`.
