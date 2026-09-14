# Заимствования

Сборка распространяется под MIT (`LICENSE`). Часть материала заимствована из
чужих проектов — их условия перечислены здесь.

## mattpocock/skills

Три правила опираются на практики из
[mattpocock/skills](https://github.com/mattpocock/skills):

- `rules/debugging-loop.md`
- `rules/session-handoff.md`
- `rules/test-discipline.md`

Заимствование указано в шапке каждого из этих файлов. Условия — MIT:

```
Copyright (c) 2026 Matt Pocock

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Оверлей 1С

Все источники ниже — под MIT, текст разрешения тот же, что выше; различаются
только правообладатели.

### Nikolay-Shirokov/cc-1c-skills

Скилл `overlays/1c/skills/1c-metadata-manage` — PowerShell-инструменты и
документация по метаданным, формам, СКД, макетам, ролям, расширениям и базам —
портирован из [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills)
и доработан: DryRun по умолчанию у мутирующих скриптов, маскирование паролей,
навигация через RLM вместо чужих MCP. Источник указан в шапке скриптов
(`# Source:`).

```
Copyright (c) 2025-2026 Nick Shirokov
```

### Desko77/claude-code-skills-1c

Правила `overlays/1c/rules/dcs-composition-recipes.md` и
`overlays/1c/rules/access-rights-bsp.md` написаны по практикам
[Desko77/claude-code-skills-1c](https://github.com/Desko77/claude-code-skills-1c)
и перепроверены по исходникам БСП; скилл `img-grid-analysis` — из того же
набора.

```
Copyright (c) 2026 Desko77
```

### brake71/1c-ssl-skills

Часть материала Desko77 о БСП сама написана по мотивам
[brake71/1c-ssl-skills](https://github.com/brake71/1c-ssl-skills); в
`access-rights-bsp.md` утверждения переписаны после сверки с исходниками БСП.

```
Copyright (c) 2026 Чекменев Дмитрий Алексеевич
```

### obra/superpowers

Методика `overlays/1c/rules/systematic-debugging.md` адаптирована из скилла
`systematic-debugging` репозитория
[obra/superpowers](https://github.com/obra/superpowers); указано в теле
правила.

```
Copyright (c) 2025 Jesse Vincent
```

## Внешний софт, не входящий в сборку

Сборка не содержит кода rlm-tools-bsl — только шаблон подключения к нему
(`overlays/1c/templates/project*.json`). Сервер ставится отдельно, условия —
его собственные: [Dach-Coin/rlm-tools-bsl](https://github.com/Dach-Coin/rlm-tools-bsl), MIT.
