---
description: "Common XML generation pitfalls for 1C metadata and managed forms (`TabularSection` `LineNumber`, `PagesGroupExtInfo` typo, `Page.enabled`, UID uniqueness, ScheduledJob method binding, post-edit validation), plus the open-time checklist for form modules of an external data processor — a built `.epf` whose form fails only when opened. Load when authoring or fixing metadata XML or `Form.xml` by hand, or before handing over a built `.epf`. Триггеры: конфигурация не загружается из файлов, ошибка загрузки XML, права роли, дублирующийся UUID, битая структура метаданных, внешняя обработка не открывается, переменная не определена при открытии формы."
alwaysApply: false
kind: invariant
---

# Common XML Generation Pitfalls (Metadata and Forms)

Concrete recurring mistakes when generating or editing 1C metadata XML / MDO and managed-form XML by hand or with scripts. Apply when authoring metadata XML directly (rather than via the `1c-metadata-manage` skill).

> Strong preference: use the `1c-metadata-manage` skill or the `metadata-manager` subagent to mutate metadata XML. The cases below are for reviewing or fixing existing files.

---

## 1. TabularSections — no `LineNumber` standard attribute

Tabular sections (`табличные части`) **must not** contain a `<standardAttributes>` block with `LineNumber`. The platform adds it automatically; an explicit copy will cause a load error or duplication.

```xml
<!-- WRONG — remove this block from <tabularSections> -->
<standardAttributes>
  <dataHistory>Use</dataHistory>
  <name>LineNumber</name>
  <fillValue xsi:type="core:UndefinedValue"/>
  <fullTextSearch>Use</fullTextSearch>
  <minValue xsi:type="core:UndefinedValue"/>
  <maxValue xsi:type="core:UndefinedValue"/>
</standardAttributes>
```

The same rule applies to MDO (EDT format) `*.mdo` files — do not add a `LineNumber` standardAttribute to tabular sections; the EDT toolchain provides it implicitly.

---

## 2. `Pages` group — correct extInfo type name

The extInfo type is `PagesGroupExtInfo` (with letter "**s**"), not `PageGroupExtInfo`:

```xml
<!-- CORRECT -->
<type>Pages</type>
<extInfo xsi:type="form:PagesGroupExtInfo">
  <pagesRepresentation>Auto</pagesRepresentation>
  <currentRowUse>Auto</currentRowUse>
</extInfo>
```

A misspelled `PageGroupExtInfo` will silently break the form — the page group will not load in Designer / EDT.

---

## 3. `Page` element — must include `<enabled>true</enabled>`

For each `Page` element inside a `Pages` group, the `<enabled>` flag is required. Without it, Designer treats the page as disabled (or the form fails validation).

```xml
<type>Page</type>
<enabled>true</enabled>
```

---

## 4. UID / UUID — must be globally unique

All UIDs and UUIDs of new metadata objects, attributes, tabular sections must be **globally unique** across the configuration.

- Generate each UUID separately via `[guid]::NewGuid()` (PowerShell) or `uuid.uuid4()` (Python).
- Never reuse a UUID by copy-paste.
- Never use placeholder / sequential UUIDs (`a1b2c3d4...`, `b2c3d4e5...`).
- After bulk metadata generation, run a duplicate-UUID check across the source tree.

When adding metadata objects — also update `Configuration.xml` (`<childObjects>` ordering matters).

---

## 5. ScheduledJob `MethodName` — fully-qualified with `CommonModule.` prefix

A `ScheduledJob`'s `<MethodName>` must be the **fully-qualified** handler reference including the metadata-class prefix, not just `Module.Method`:

```xml
<!-- WRONG — load fails: "Ссылка на неизвестный метод" / "Имя метода должно быть задано" -->
<MethodName>МойОбщийМодуль.МойОбработчик</MethodName>

<!-- CORRECT -->
<MethodName>CommonModule.МойОбщийМодуль.МойОбработчик</MethodName>
```

The handler must be an exported procedure of a non-global **server** common module (`<Server>true</Server>`). Match the serialization of the existing base-config jobs (the same `CommonModule.<Module>.<Method>` shape). Without the prefix, load-from-files fails the job's method-binding validation even though the procedure exists.

---

## 6. Role `Rights.xml` — no rights on enums

Enums are readable by everyone without restriction, so an explicit rights block
for `Enum.<Name>` in a role is redundant. Types that never appear in
`Rights.xml` at all: `Enum`, `FunctionalOption`, `DefinedType`, `CommonModule`,
`CommonPicture`, `CommonTemplate` (the `1c-metadata-manage` skill, `role-manage`
doc, lists them with the full rights vocabulary).

```xml
<!-- WRONG — belongs in no role, neither in an extension nor in the base config -->
<object>
    <name>Enum.СтатусыОбработки</name>
    <right><name>Read</name><value>true</value></right>
    <right><name>View</name><value>true</value></right>
</object>
```

> **Suspect first when an extension load hangs.** External practice reports
> `DESIGNER /LoadConfigFromFiles -Extension` on platform 8.3.27 hanging for
> 60+ seconds with an empty `/Out` and no error when a role's `Rights.xml`
> contains a rights block on a **new** enum; EDT is reported to generate such a
> block on export. **Not reproduced on our contour** — treat it as the first
> hypothesis for a silent load hang, not as an established fact. Reviewing
> `Rights.xml` for `Enum.*` blocks is worth doing regardless: the block is
> redundant either way.
>
Rights in a role file are the static half of access control. The runtime half —
access-group profiles, assigning them to users, checking a right or a role from
code — is `access-rights-bsp.md`, and it has its own silent-failure mode
(a profile that saves with its roles quietly dropped).

> The same source reports the same hang shape when a **new metadata object and
> a role granting rights on it** arrive in one export, with a two-pass load
> (object first, rights second) as the workaround. Equally unverified here —
> worth trying when a load hangs, not worth splitting every export in two.

---

## 7. Type qualifiers that break restructuring

Both traps below surface the same way — «Ошибка SDBL: Слишком большое значение
описателя длины» when the platform restructures the table — and both are
invisible in the XML until then.

**String: 1024 is the inline ceiling.** A fixed-length string attribute holds at
most 1024 characters. For longer text set the length to `0` (unlimited, stored
as a LOB) rather than raising the number.

```xml
<v8:StringQualifiers>
  <v8:Length>250</v8:Length>      <!-- fixed -->
</v8:StringQualifiers>
<v8:StringQualifiers>
  <v8:Length>0</v8:Length>        <!-- unlimited, LOB -->
</v8:StringQualifiers>
```

**Number: state the fractional part explicitly**, even when it is zero. An
absent fractional-digits qualifier is not read as "zero" during restructuring —
it is read as the maximum the precision allows.

```xml
<v8:NumberQualifiers>
  <v8:Digits>10</v8:Digits>
  <v8:FractionDigits>0</v8:FractionDigits>   <!-- never omit -->
  <v8:AllowedSign>Any</v8:AllowedSign>
</v8:NumberQualifiers>
```

> **Element names differ by source format.** The above is the Configurator dump
> (`<v8:Digits>` / `<v8:FractionDigits>`). In EDT `.mdo` sources the same two
> are `<precision>` / `<scale>`, and the EDT normalizer is reported to strip
> `<scale>0</scale>` as a default — on an EDT project, check for it after the
> linter runs. Do not carry the EDT spelling into Configurator XML: the
> qualifier will simply be ignored.

A check worth running after bulk generation: no string length above 1024, and
every `NumberQualifiers` block carrying its fractional-digits element.

---

## 8. `ConfigDumpInfo.xml` — the index that silently skips new objects

`/LoadConfigFromFiles` treats `ConfigDumpInfo.xml` as an **index** and loads
incrementally by it. Files of new objects that the index does not list are
ignored **silently**, while the updated `Configuration.xml` loads anyway — the
result is a configuration that references objects it does not contain.

Symptom: the load reports success, the new objects are simply absent from the
storage.

Either regenerate the index, or delete it so the load is full.

## 9. `RegisterRecordsDeletion` — one valid value, one plausible wrong one

The document property that clears movements on unposting is written as
`RegisterRecordsDeletion` with the value `AutoDeleteOnUnpost`. The shorter
`AutoDeleteOn` looks like a valid enum member and is not — the load fails on
it.

## 10. Validation hook

Whenever editing metadata XML by hand, after the change run:

- Validation from the `1c-metadata-manage` skill or project metadata validation scripts (`1c-meta-validate`, form validation, compile/load smoke where available).
- A dedicated XML schema validator only if the current session actually exposes one — validate against the appropriate XSD (fetch the schema for the target metadata type first if unsure).
- A duplicate-UUID scan across the source tree after bulk generation.

This catches structural issues (missing required elements, wrong type names, broken references) before they reach the platform.

## 11. Form modules of an external data processor compile only at open time

Building an `.epf` via `/LoadExternalDataProcessorOrReportFromFiles` does **not**
compile form modules, and BSL LS checks neither the validity of platform names
nor client/server availability. Every defect below shipped inside a successfully
built `.epf` and surfaced only when a person opened the form. Before handing over
an `.epf`, walk the form module against this checklist.

1. **Invented platform names.** Extract every call not defined in the module and
   confirm each against the platform documentation, not from memory. Names that
   shipped: `СтрРЗаменить`, `ПолучитьФайлАсинх` (real:
   `ПолучитьФайлССервераАсинх`), `ЧтениеXML.ЧитатьДальше` / `.ИмяУзла` /
   `.УзелXML` (real: `Прочитать` / `Имя` / `ТипУзла`), `ДобавитьКДате` and
   `ЧастьДаты` in BSL code (query language only — in code use `ДобавитьМесяц`).
2. **Client context.** In `&НаКлиенте` sections: no `ТекущаяДатаСеанса`
   (server-only — compute on the server and return it in the result structure),
   no queries and no serializers. Saving a file to a user folder —
   `ПолучитьФайлССервераАсинх`; picking a folder — `ДиалогВыбораФайла` +
   `ВыбратьФайлАсинх`.
3. **Temp storage owner.** `ПоместитьВоВременноеХранилище` needs the form
   `УникальныйИдентификатор` passed in from the client, otherwise the address
   dies at the end of the server call.
4. **Main form attribute name.** Scaffolding emits `Attribute name="Object"`
   while a Russian module refers to `Объект` — "Переменная не определена" at form
   open. Rename the attribute (and its `DataPath` prefix) to match the module.
5. **Form property collisions.** A local variable named like a read-only form
   property fails at **runtime**, not at compile time: `ИмяФормы = ...` →
   "Поле объекта недоступно для записи". Cross-check assigned names against the
   properties of `УправляемаяФорма` (`form-reserved-names.md`).
6. **Server-side attach of external files.** Since 8.3.9
   `ВнешниеОбработки.Подключить` on the server accepts **only** a temp-storage
   address; a file path raises "Неправильный путь к файлу". Read the file into
   `ДвоичныеДанные`, put it into temp storage (form UUID as owner), attach by
   address.
7. **Server code never sees client paths.** On a client-server infobase a
   `&НаСервере` routine opening a user-profile path runs inside `rphost` on the
   application server — "Каталог не обнаружен" even though the folder exists on
   the client machine. File exchange with the user's machine goes through temp
   storage only: the server writes into its own `ПолучитьИмяВременногоФайла()`
   directory → `ПоместитьВоВременноеХранилище` → the client saves via
   `ПолучитьФайлССервераАсинх`. **A file infobase masks this defect** (client and
   server are the same machine) — it surfaces only in production.
8. **Query literals.** Quotes inside a string literal comment must be doubled
   (a bare `"` splits the literal). A table alias must not be a reserved word,
   and must not equal a field alias in the same query — otherwise
   "неоднозначное поле".
9. **Number + string concatenation.** `Счетчик + " объектов"` fails with
   "Преобразование значения к типу Число": the type of the **left** operand wins.
   Start the concatenation with a string, or wrap numbers in `Строка()`.
10. **Register manager collections.** Not every register that carries movements
    is an accumulation register — look the type up in the sources before
    indexing `РегистрыНакопления[...]`; a `РегистрСведений` subordinate to a
    recorder is a common shape.
11. **Serialized objects carry extension attributes.** XML exported from a base
    with installed extensions contains their attributes (prefixed names) in the
    current-configuration namespace; a strict `СериализаторXDTO` on a base
    without those extensions rejects the whole file
    ("НачалоСвойства: ..."). Strip such elements before deserialization —
    self-closed tags first, then paired ones.
12. **Copy-from-sibling drift.** Code copied from another processor carries its
    pre-fix defects — re-run this checklist on pasted fragments too.

The checklist is the cheap pass; the **mechanical gate for this whole class is
opening the built `.epf` in a test client** — that open is the only compilation
of a form module there is. If the project has a UI-test contour, wire an
open-check scenario per built processor into it and run it after the build; the
contour's own documentation describes what such a gate needs (library steps,
an extension permitting external files on the test infobase, and the platform's
unsafe-action protection lifted for test infobases only).

Cheap automation next to it: a script that lists call names undefined in the
module, scans `&НаКлиенте` bodies for server-only names, and checks quote parity
and per-query alias clashes catches most of the list in seconds.
