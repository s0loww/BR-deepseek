"""Тесты tj.py на синтетических фикстурах. Запуск: python test_tj.py

Фикстуры написаны руками и содержат ловушки формата: многострочные значения в
обеих кавычках, удвоенная кавычка внутри значения, строка, похожая на начало
события, внутри текста запроса, событие без свойств, формат времени 8.2.
Реальный журнал сюда класть нельзя: в нём пользователи, адреса и данные.
"""
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import tj  # noqa: E402

CURRENT = HERE / "fixtures" / "current"
LEGACY = HERE / "fixtures" / "legacy"
SECRETS = ("Иванов", "Петров", "Сидоров", "PC-DEMO", "СЕКРЕТ", "8a2b000000000000", "0x9A3B")


def run(*argv):
    return tj.run([str(a) for a in argv])


def rows(rep, title_part):
    for sec in rep["sections"]:
        if title_part in sec["title"]:
            return sec["rows"]
    raise AssertionError(f"нет секции «{title_part}»: {[s['title'] for s in rep['sections']]}")


def by_first(table):
    return {r[0]: r for r in table}


class Parsing(unittest.TestCase):
    def test_event_counts_survive_quoted_multiline_values(self):
        code, rep, _ = run("inventory", CURRENT)
        self.assertEqual(code, 0)
        counts = {r[0]: r[1] for r in rows(rep, "События")}
        self.assertEqual(counts, {"CALL": 3, "DBMSSQL": 2, "TLOCK": 2, "TTIMEOUT": 1,
                                  "TDEADLOCK": 1, "EXCP": 2, "QERR": 1})

    def test_doubled_quote_inside_value(self):
        self.assertEqual(tj.parse_props(",Descr='a ''b'', c',X=1"), {"Descr": "a 'b', c", "X": "1"})

    def test_quote_state_across_lines(self):
        self.assertEqual(tj.quote_state("x=1,Context='\n", None), "'")
        self.assertEqual(tj.quote_state("inner 'quoted'' text\n", "'"), None)
        self.assertEqual(tj.quote_state("still ''doubled'' inside\n", "'"), "'")

    def test_legacy_duration_unit(self):
        code, rep, _ = run("slowest", LEGACY, "--event", "CALL")
        self.assertEqual(code, 0)
        self.assertEqual(rows(rep, "Самые долгие")[0][3], 2500.0)
        journal = by_first(rows(run("inventory", LEGACY)[1], "Журнал"))
        self.assertIn("десятитысячные", journal["единица длительности"][1])

    def test_crlf_and_bom(self):
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "rphost_1111"
            dst.mkdir()
            for f in (CURRENT / "rphost_1111").glob("*.log"):
                data = f.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
                (dst / f.name).write_bytes(b"\xef\xbb\xbf" + data)
            self.assertEqual(rows(run("inventory", tmp)[1], "События"),
                             rows(run("inventory", CURRENT)[1], "События"))

    def test_zip_equals_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            arc = Path(tmp) / "tj.zip"
            with zipfile.ZipFile(arc, "w") as zf:
                for f in CURRENT.rglob("*.log"):
                    zf.write(f, f.relative_to(CURRENT).as_posix())
            self.assertEqual(rows(run("inventory", arc)[1], "События"),
                             rows(run("inventory", CURRENT)[1], "События"))


class Commands(unittest.TestCase):
    def test_top_calls_by_module(self):
        top = by_first(rows(run("top", CURRENT, "--event", "CALL", "--by", "module")[1], "Топ"))
        self.assertEqual(top["ОбщийМодуль.Демо.Провести"][1:3], [2, 3.0])
        self.assertEqual(top["ОбщийМодуль.Отчеты.Сформировать"][1], 1)

    def test_top_context_is_innermost_frame(self):
        rep = run("top", CURRENT, "--event", "DBMSSQL", "--by", "context")[1]
        self.assertEqual([r[0] for r in rows(rep, "Топ")],
                         ["Документ.Демо.МодульОбъекта : 10 : Запрос.Выполнить();"])

    def test_queries_differing_in_literals_share_fingerprint(self):
        (row,) = rows(run("top", CURRENT, "--event", "DBMSSQL", "--by", "sql", "--sql")[1], "Топ")
        self.assertTrue(row[0].startswith("q:"))
        self.assertEqual(row[1], 2)
        self.assertIn("TOP ?", row[-1])
        self.assertIn("T1._Fld10", row[-1])

    def test_locks(self):
        rep = run("locks", CURRENT)[1]
        total = {r[0]: r[1] for r in rows(rep, "Итог")}
        self.assertEqual(total["TLOCK с ожиданием другого соединения"], 1)
        self.assertEqual(total["суммарное ожидание, с"], 0.8)
        self.assertEqual(total["TTIMEOUT (таймауты ожидания)"], 1)
        self.assertEqual(total["TDEADLOCK (взаимоблокировки)"], 1)
        self.assertEqual(rows(rep, "Взаимоблокировки")[0][2], "InfoRg30.DIMS")
        self.assertEqual(rows(rep, "по месту кода")[0][0],
                         "РегистрСведений.Демо.МодульНабораЗаписей : 5 : Блокировка.Заблокировать();")

    def test_errors(self):
        rep = run("errors", CURRENT)[1]
        self.assertTrue(any(n.startswith("EXCP: 1 событий записаны без свойств") for n in rep["notes"]), rep["notes"])
        places = {r[1] for r in rows(rep, "Ошибки")}
        self.assertIn("Документ.Демо.МодульОбъекта : 50 : ВызватьИсключение Текст;", places)
        self.assertIn("Документ.Демо.МодульОбъекта : 60 : Запрос.Выполнить();", places)
        self.assertIn("(нет Context)", places)

    def test_hour_and_infobase_filters(self):
        counts = {r[0]: r[1] for r in rows(run("inventory", CURRENT, "--to", "26010110")[1], "События")}
        self.assertEqual(counts["CALL"], 2)
        rep = run("top", CURRENT, "--event", "CALL", "--by", "infobase", "--infobase", "other_ib")[1]
        self.assertEqual([r[0] for r in rows(rep, "Топ")], ["other_ib"])

    def test_inventory_says_when_calls_are_not_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "rphost_9"
            d.mkdir()
            (d / "26010110.log").write_text(
                "00:20.000001-15,TLOCK,4,process=rphost,Regions=A1.DIMS,WaitConnections=,Context=x\n",
                encoding="utf-8")
            rep = run("inventory", tmp)[1]
            answers = by_first(rows(rep, "На какие вопросы"))
            self.assertEqual(answers["долгие серверные вызовы"][1], "нет")
            self.assertEqual(answers["долгие запросы к СУБД"][1], "нет")
            self.assertTrue(any("logcfg" in n for n in rep["notes"]))
            self.assertEqual(run("top", tmp, "--event", "CALL")[0], 1)

    def test_exit_codes_and_report_file(self):
        self.assertEqual(run("top", CURRENT, "--event", "SDBL")[0], 1)
        self.assertEqual(run("inventory", CURRENT / "нет-такого")[0], 2)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "locks.json"
            proc = subprocess.run([sys.executable, str(HERE / "tj.py"), "locks", str(CURRENT), "--out", str(out)],
                                  capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["command"], "locks")


class Privacy(unittest.TestCase):
    def assert_clean(self, rep, argv):
        text = tj.to_markdown(rep) + json.dumps(rep, ensure_ascii=False)
        for secret in SECRETS:
            self.assertNotIn(secret, text, f"{argv}: в выводе {secret}")

    def test_default_output_has_no_users_hosts_or_data(self):
        for argv in (["inventory"], ["top"], ["top", "--by", "sql"], ["top", "--by", "stack"],
                     ["slowest"], ["locks"], ["errors"]):
            self.assert_clean(run(argv[0], CURRENT, *argv[1:])[1], argv)

    def test_sql_flag_shows_structure_without_literals(self):
        for argv in (["top", "--event", "DBMSSQL", "--by", "sql", "--sql"], ["slowest", "--sql"]):
            self.assert_clean(run(argv[0], CURRENT, *argv[1:])[1], argv)

    def test_descr_flag_is_the_explicit_way_to_see_error_text(self):
        rep = run("errors", CURRENT, "--descr")[1]
        self.assertIn("СЕКРЕТ", tj.to_markdown(rep))


if __name__ == "__main__":
    unittest.main(verbosity=1)
