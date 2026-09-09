# Контракт Kun: что среда читает и чего в ней нет

Справочник по целевой среде. Собран 2026-09-09 из двух источников: доки
репозитория [KunAgent/Kun](https://github.com/KunAgent/Kun) и разбор
установленного билда (`resources/app.asar`) плюс рантайм-конфиг на машине.
Всё, что ниже, проверено; предположения помечены явно.

## Что такое Kun

Локальный агентский воркбенч (Electron GUI + TUI), open-source, **не**
продукт DeepSeek. Раньше назывался deepseek-gui — на машине это видно по
`%APPDATA%/Kun/.migrated-from-deepseek-gui.json`. Официальной CLI или IDE у
DeepSeek нет; из вендорского есть только API и anthropic-совместимый
endpoint для Claude Code.

## Где что лежит

| Что | Путь |
| --- | --- |
| Настройки GUI | `%APPDATA%/Kun/kun-settings.json` (macOS: `~/Library/Application Support/Kun/`, Linux: `~/.config/Kun/`) |
| Конфиг рантайма | `~/.kun/data/config.json` (или `<dataDir>/config.json`) |
| Глобальные скиллы | `~/.kun/skills/` |
| Глобальный MCP | `~/.kun/mcp.json` |
| Проектная политика | `<workspace>/.kun/project.json` |
| Проектные роли | `<workspace>/.kun/agents/*.md` |
| Проектные скиллы | `<workspace>/.kun/skills/` + conventional roots |
| Инструкции проекта | `<workspace>/AGENTS.md` (и `CLAUDE.md` — распознаётся) |

## Инструкции проекта

Kun читает `AGENTS.md` нативно и **инжектит его в каждый turn** — настройка
«AGENTS.md instructions» (описание в билде: *«Inject Kun-native global and
workspace AGENTS.md files into every turn»*). Глобальный и воркспейсный
файлы складываются.

Следствие для раскладки: корневой контракт оплачивается на каждом ходу.
Тела правил туда не кладут — они лежат в `rules/` и читаются по индексу.

## Роли субагентов

Файлы `.kun/agents/<role>.md`, в GUI помечены как read-only с подписью
«Edit this role in .kun/agents/*.md». Из markdown-оверлея читаются поля:

```
id, name, description, mode (subagent|primary|all),
toolPolicy (readOnly|inherit), color, systemPrompt, promptPreamble,
allowedTools, blockedTools
```

Тело файла — промпт роли. Категории встроенного каталога:
`development`, `review`, `quality`, `planning`, `operations`, `research`,
`custom`.

**Модели и усилия в файле роли нет.** Субагент идёт на модели сессии, если в
Settings → Agents не выставлен per-agent override. Тиры в
`agents/ROLES.md` — рекомендация по настройке, а не то, что файл включает
сам.

## Скиллы

Формат `SKILL.md` с YAML-frontmatter (`id`, `name`, `description`). Корни
сканирования, в порядке приоритета:

1. явные `skills.roots` из `.kun/project.json`;
2. conventional roots проекта — `.agents/skills`, `.claude/skills`,
   `.codex/skills`, `.kun/skills`, `skills`;
3. воркспейсные корни из GUI;
4. глобальные и плагинные корни.

Первый скилл с совпадающим нормализованным id побеждает. Практический
вывод: скиллы, написанные под Claude Code, Kun подхватывает без правок.

## MCP

Проектный `.kun/project.json`, строгая схема, обязательный `"version": 1`:

```json
{
  "version": 1,
  "mcp": { "servers": { "<id>": { "transport": "stdio|streamable-http|sse", "command": "...", "args": [], "cwd": "." } } },
  "skills": { "enabled": true, "includeConventional": true, "roots": [], "disabledIds": [] }
}
```

Репозиторий **не может одобрить сам себя**: открытие проекта не запускает
его MCP. Одобрение — вручную в Settings → Agents → Project MCP & Skills,
Kun привязывает грант к SHA-256 дайджесту файла и хранит его локально
(`agents.kun.projectConfig.grants`), в репозиторий ничего не пишет. Проект
не может объявлять `trustScope`, `trustedWorkspaceRoots`, `workspaceRoots`.

Все пути (`skills.roots`, `cwd`) обязаны быть относительными и лежать
внутри воркспейса: абсолютные пути, `..`, симлинки наружу — отклоняются.

## Хуки

Шесть фаз: `PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `TurnStart`,
`TurnEnd`, `PreCompact`. Режимы: `observe`, `block`, `rewrite`. Протокол
внешней команды сознательно повторяет Claude Code — JSON на stdin, exit 2
блокирует, JSON на stdout; `UserPromptSubmit` умеет вернуть
`additionalContext`. Семантика отказов: инструментальные фазы падают
закрыто, инъекция в промпт — открыто, наблюдатели только предупреждают.

**Конфигурируются глобально** — массив `hooks` верхнего уровня в
`~/.kun/data/config.json`, не в репозитории. Положить хук в проект
инсталлятором нельзя.

## Модели, усилие, контекст

Из рантайм-конфига на машине (provider `deepseek`):

- модели: `deepseek-v4-pro`, `deepseek-v4-flash`;
- `contextWindowTokens`: 1 000 000 у обеих;
- `supportedEfforts`: `["off", "high", "max"]`, `defaultEffort`: `max`;
- `endpointFormat`: `chat_completions`, baseUrl `https://api.deepseek.com`;
- компакция: `defaultSoftThreshold` 192 000, `defaultHardThreshold` 217 600.

**Рабочее окно — примерно 190k, а не миллион.** До объявленного контекста
дело не доходит: Kun начинает сжимать раньше.

## Чего в Kun нет

- **Файловых слэш-команд.** Слэш-команды встроенные (`/new`, `/research`,
  …), каталога кастомных команд нет. Команды из upstream-дистрибутива не
  переносятся — эквивалент делается скиллом или правилом.
- **Поля модели/усилия в роли** — см. выше.
- **Проектных хуков** — только машинно-глобальные.

## Как перепроверить, когда билд обновится

```bash
python -c "import json;d=json.load(open(r'C:\Users\<user>\.kun\data\config.json'));print(json.dumps(d['serve']['providers'],indent=1)[:2000])"
```

Строки контракта ищутся в бандле:

```bash
python -c "import re;d=open(r'C:\Users\<user>\AppData\Local\Programs\Kun\resources\app.asar','rb').read();m=re.search(rb'function workspaceProfileToKun',d);print(d[m.start():m.start()+800].decode('latin1'))"
```
