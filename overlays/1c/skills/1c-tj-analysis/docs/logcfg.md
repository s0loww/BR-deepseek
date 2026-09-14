# Настройка технологического журнала под поиск долгих вызовов

Журнал отвечает только на те вопросы, под которые его настроили. Типичная
ошибка — включить `TLOCK` целиком: получаются сотни тысяч захватов в час, а
ни длительностей вызовов, ни текстов долгих запросов в журнале нет.

## Куда класть

`logcfg.xml` — в каталог `conf` платформы на сервере 1С (путь задаёт
`conf.cfg`, параметр `ConfLocation`). Файл подхватывается без перезапуска
сервера в течение минуты. Каталог журнала (`location`) — на диске с
запасом места и **отдельный** под каждую настройку: платформа удаляет из
него всё, что старше `history` часов.

## Рецепт: долгие вызовы и запросы

```xml
<?xml version="1.0" encoding="UTF-8"?>
<config xmlns="http://v8.1c.ru/v8/tech-log">
  <log location="D:\techlog\slow" history="48">
    <event>
      <eq property="name" value="CALL"/>
      <ge property="durationus" value="1000000"/>
    </event>
    <event>
      <eq property="name" value="SCALL"/>
      <ge property="durationus" value="1000000"/>
    </event>
    <event>
      <eq property="name" value="DBMSSQL"/>
      <ge property="durationus" value="500000"/>
    </event>
    <event>
      <eq property="name" value="SDBL"/>
      <ge property="durationus" value="500000"/>
    </event>
    <event>
      <eq property="name" value="TTIMEOUT"/>
    </event>
    <event>
      <eq property="name" value="TDEADLOCK"/>
    </event>
    <event>
      <eq property="name" value="EXCP"/>
    </event>
    <property name="all"/>
  </log>
</config>
```

- Пороги: вызовы от 1 с, запросы от 0,5 с. Если журнал всё равно большой —
  поднять; если пустой, а жалобы есть — опустить.
- Для PostgreSQL вместо `DBMSSQL` — `DBPOSTGRS`.
- `<property name="all"/>` пишет все свойства, включая тексты запросов и
  пользователей. Это то, что нужно для разбора, и то, что нельзя
  отправлять наружу без согласия.
- Ожидания блокировок без всех захватов — `TLOCK` с непустым
  `WaitConnections`:

  ```xml
  <event>
    <eq property="name" value="TLOCK"/>
    <ne property="WaitConnections" value=""/>
  </event>
  ```

## Единицы длительности

В 8.3 фильтр `durationus` — в микросекундах (`1000000` = 1 с). Старое
свойство `duration` — в десятитысячных долях секунды (`10000` = 1 с) и
оставлено для совместимости. Сведения — из практических статей
([Infostart: примеры настроек ТЖ](https://infostart.ru/1c/articles/2020498/),
[Infostart: мониторинг производительности](https://infostart.ru/1c/articles/1040073/));
**перед боевой настройкой сверить с описанием `logcfg.xml` на ИТС для своей
версии платформы**. Фильтр `ne` по `WaitConnections` тоже взят из практики, а
не из документации.

## После сбора

- Снимать в часы жалоб, а не «сутки на всякий случай».
- Настройку убрать или переименовать файл, когда журнал собран: включённый
  журнал с `property all` постоянно пишет на диск.
- Разбирать скриптом скилла, начиная с `inventory`.
