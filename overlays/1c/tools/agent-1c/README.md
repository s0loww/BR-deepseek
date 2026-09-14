# agent-1c

Переносимый Windows-контур для обнаружения платформы 1С, статической проверки,
безопасного развёртывания тестовой ИБ и смоук-тестирования 1С-проектов. Весь
проектный контекст (пути, имена баз, креды, имя расширения) вынесен в
**профиль проекта** — `agent-1c.json` в корне целевого репозитория. Сам контур
проектных привязок не содержит.

Полный рецепт «до боевого состояния» (baseline-политика, портативная установка
тест-стека, боевые грабли Vanessa) — в [DEPLOYMENT.md](DEPLOYMENT.md). Здесь —
краткий справочник.

## Команды (из корня проекта)

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/agent-1c/agent-1c.ps1 bootstrap -Profile agent-1c.json
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/agent-1c/agent-1c.ps1 doctor    -Profile agent-1c.json
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/agent-1c/agent-1c.ps1 analyze   -Profile agent-1c.json
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/agent-1c/agent-1c.ps1 deploy    -Profile agent-1c.json
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/agent-1c/agent-1c.ps1 test      -Profile agent-1c.json
```

- `deploy` всегда DryRun; мутация — только с `-Apply` и только для цели
  `test`/`development`. `environment: production` блокируется до запуска платформы.
- `analyze` возвращает код `4`, если BSL LS нашёл диагностики уровня `Error` —
  это не сбой установки, а состояние исходников (см. baseline-политику в DEPLOYMENT).
- `test` возвращает код `3`, если тест-стек (vanessa-runner / Vanessa-Automation)
  не установлен или тестовая ИБ не настроена.

Профиль не найден → команда падает с понятной ошибкой; путь профиля задаётся
`-Profile`, а `sourceDir`/`resultDir` вычисляются относительно каталога профиля.

## Если исходники — это РАСШИРЕНИЕ конфигурации

Критично. Если `sourceDir` содержит **расширение** (в `Configuration.xml` →
`Properties/Name` стоит имя расширения, а не основной конфигурации), голые
`/LoadConfigFromFiles` + `/UpdateDBCfg` **перезапишут основную конфигурацию базы**.
Чтобы этого не случилось, задайте в профиле блок `extension`:

```json
"extension": { "name": "{{ИмяРасширения}}" }
```

Когда `extension.name` задан, `deploy` подставляет:

- к `/LoadConfigFromFiles` — `-Extension {{ИмяРасширения}} -Format Hierarchical`;
- к `/UpdateDBCfg` — `-Extension {{ИмяРасширения}}`.

Если блок `extension` убрать (или `name: null`), поведение возвращается к работе
с основной конфигурацией. **Для проекта-расширения этот блок обязателен.**

## Креды и путь тестовой ИБ

`testTarget` берёт путь ИБ, логин и пароль в таком приоритете:

1. переменные окружения, чьи имена заданы в `userEnv` / `passwordEnv`;
2. INI-секция файла окружения — поля `envFile` (путь к `.env`) и `envSection`
   (имя секции), ключи `Path` / `Login` / `Pass`.

Пароль нигде не печатается: в строке команды для лога он заменяется на `<hidden>`,
файл окружения только читается. Конкретные имена секции/переменных и путь `.env`
живут в **проектном профиле** `agent-1c.json`, а не в этом контуре.

## Установка тест-стека (портативно)

Без изменения глобального PATH, всё под `%LOCALAPPDATA%\agent-1c\tools`:

- BSL Language Server — командой `bootstrap` (архив проверяется по SHA-256 из
  `toolchain.lock.json`);
- OneScript + `opm`, затем `vanessa-runner` через `opm` — в
  `%LOCALAPPDATA%\agent-1c\tools\onescript`;
- Vanessa-Automation — **только свежий VA-single релиз** в
  `%LOCALAPPDATA%\agent-1c\tools\vanessa\<версия>\vanessa-automation-single.epf`.

`doctor` и `test` находят `vrunner` в PATH либо в `...\onescript\bin`. Полная
пошаговая установка стека — в DEPLOYMENT.md §3.

## Смоук-тесты Vanessa-Automation (`test`)

Suite-скелет shipped рядом с контуром — каталог `vanessa-suite/`:

- `features/smoke.feature` — минимальный стабильный сценарий: тонкий тест-клиент
  подключается к тестовой ИБ, окна закрываются, **данные базы не меняются**;
- `vanessa-settings.template.json` — шаблон настроек `vanessa-runner` (`--settings`,
  формат `env.json`) с плейсхолдерами `{{IB_CONNECTION}}` / `{{LOGIN}}` /
  `{{V8VERSION}}`. **Пароля не содержит;**
- `vanessa-add-params.template.json` — шаблон настроек фреймворка VA
  (`--vanessasettings`): тонкий клиент, `ДанныеКлиентовТестирования`, таймаут
  запуска, отчёт jUnit, автозакрытие. Пароль — только плейсхолдером `{{PASSWORD}}`.

`test` рендерит оба шаблона во **временные** файлы прогона (UTF-8 **с BOM**,
имена **без ведущей точки**), запускает `vrunner vanessa`, санирует логи и
удаляет временный VAParams в `finally`. Пароль в репозитории не хранится никогда.
Клиент — **тонкий** (`ordinaryApp: 0`), таймаут тест-клиента — `testClientTimeoutSeconds`
(по умолчанию 300 с: дефолтные 25 не переживают первый старт тяжёлой конфигурации).

Отчёты и логи — в `resultDir/<timestamp>-test/`: `reports/junit/`,
`reports/buildstatus.log`, `reports/vanessaonline.txt`, `vanessa-stdout.log` /
`vanessa-stderr.log`, унифицированный `result.json`.

### Грабли VA + vrunner (проверены живыми прогонами)

1. **«Не удалось прочитать файл настроек JSON»** (модалка VA): VA не переваривает
   нестандартные ключи `$schema` / `_comment` в VAParams и не читает settings-файл,
   чьё имя начинается с точки. Поэтому VAParams — без комментариев-ключей, temp-файлы
   — без ведущей точки, кодировка — **UTF-8 с BOM** (без BOM на ru-Windows файл
   читается как windows-1251 и кириллические ключи ломаются).
2. **Пароль тест-клиента**: `vrunner` передаёт `/P` только тест-**менеджеру**;
   профиль «Этот клиент» VA собирает без пароля → интерактивное окно логина →
   «Не получилось подключить TestClient. Прерывание по таймауту». Лечение — блок
   `ДанныеКлиентовТестирования` в VAParams, где логин/пароль тест-клиента уходят
   в `ДопПараметры`: `/N"{{LOGIN}}" /P"{{PASSWORD}}"`. Поле порта **не задавать**
   (`ПортЗапуска` VA не признаёт; дефолтный порт 48000 рабочий).
3. **Таймауты**: `ТаймаутЗапуска1С=300` (дефолтные 25 с не переживают старт тяжёлой
   базы), `КоличествоСекундПоискаОкна=120`.
4. **Обязательные ключи статуса** (иначе `vrunner` падает «Не найден файл статуса»):
   `ВыгружатьСтатусВыполненияСценариевВФайл`,
   `ПутьКФайлуДляВыгрузкиСтатусаВыполненияСценариев`, `ИмяФайлаЛогВыполненияСценариев`.
5. **Гигиена секретов**: тест-менеджеру пароль уходит переменной окружения
   `RUNNER_DBPWD`; временный VAParams затирается и удаляется в `finally`; логи
   санируются (точный секрет + паттерн `/P"***"` → `<hidden>`); `.ps1` и `.feature`
   — UTF-8 **с BOM** (PS 5.1 иначе портит кириллицу).
6. Несовместимость: opm-пакет `add` (bddRunner.epf 6.8.0) с платформами 8.3.27+
   падает «Преобразование значения к типу Число» — используйте только свежий
   VA-single релиз (`test` выбирает его автоматически).

## Инструменты и отчёты

Инструменты ставятся в `%LOCALAPPDATA%\agent-1c\tools`, отчёты — в
`resultDir/<timestamp>-<command>/` (каталог `var/` целевого проекта — в
`.gitignore`). Платформа 1С не скачивается: контур находит новейшую установленную
версию с `platform.versionPrefix` либо использует явный `platform.executable` из
профиля.

## Что почитать перед подключением

- [DEPLOYMENT.md](DEPLOYMENT.md) — полный рецепт развёртывания «до боевого
  состояния»: baseline-политика, `-Extension` при деплое расширения, портативная
  установка тест-стека, боевые грабли, критерий готовности.
- `rules/script-contract.md` — generic-контракт автоматизационных скриптов
  (DryRun/Apply, exit-коды, отчёты, обращение с кредами).
- `rules/com-powershell-1c.md` — грабли COM/PowerShell 1С.
