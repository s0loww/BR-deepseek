"""Симуляция совмещённой раскладки для install/kun_split.py. Запуск: python ci/test_kun_split.py

Клонирует сборку из этого репозитория во временный каталог (закоммиченное
состояние, git нужен), ставит в клон 1С-проект «в себя» — как это случилось в
реальной установке, — подкладывает правки и файлы проекта, затем проходит
процедуру install/split-layout.md: чистый клон, установка в отдельную папку,
перенос, проверка. Отдельно — ветки, где скрипт обязан остановиться.
"""
import contextlib
import io
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "install"))
import kun_split  # noqa: E402


def install(src, dst):
    """Шаги раздела «Установка в проект» из overlays/1c/README.md."""
    ov = src / "overlays/1c"
    for d in ("rules", ".kun/agents", ".kun/skills", "tools"):
        (dst / d).mkdir(parents=True, exist_ok=True)

    def put(a, b):
        if Path(a).resolve() != Path(b).resolve():
            shutil.copyfile(a, b)

    put(ov / "templates/AGENTS.md", dst / "AGENTS.md")
    for f in list((src / "rules").glob("*.md")) + list((ov / "rules").glob("*.md")):
        put(f, dst / "rules" / f.name)
    for f in list((src / "agents/roles").glob("*.md")) + list((ov / "agents/roles").glob("*.md")):
        put(f, dst / ".kun/agents" / f.name)
    for base in (src / "skills", ov / "skills"):
        for d in base.iterdir():
            if d.is_dir():
                shutil.copytree(d, dst / ".kun/skills" / d.name, dirs_exist_ok=True)
    for d in (ov / "tools").iterdir():
        shutil.copytree(d, dst / "tools" / d.name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
    put(ov / "templates/project.json", dst / ".kun/project.json")
    put(ov / "dev.env.example", dst / ".dev.env.example")


def fill(agents_md):
    import re
    agents_md.write_text(re.sub(r"\{\{[A-Z_]+\}\}", "заполнено", agents_md.read_text(encoding="utf-8")),
                         encoding="utf-8")


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = kun_split.main([str(a) for a in argv])
    return code, out.getvalue()


def _unlock(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)
    func(path)


class SplitLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="kun-split-"))
        cls.x, cls.b, cls.p = cls.tmp / "X", cls.tmp / "B", cls.tmp / "P"
        for target in (cls.x, cls.b):
            subprocess.run(["git", "clone", "-q", str(ROOT), str(target)], check=True)
        install(cls.x, cls.x)
        fill(cls.x / "AGENTS.md")
        (cls.x / ".dev.env").write_text("PREFIX=тест_\n", encoding="utf-8")
        (cls.x / "src/CommonModules/Демо/Ext").mkdir(parents=True)
        (cls.x / "src/CommonModules/Демо/Ext/Module.bsl").write_text("Процедура А()\nКонецПроцедуры\n", encoding="utf-8")
        (cls.x / ".venv/Lib").mkdir(parents=True)
        (cls.x / ".venv/Lib/site.txt").write_text("venv\n", encoding="utf-8")
        with open(cls.x / "rules/delegation.md", "a", encoding="utf-8") as fh:
            fh.write("\n<!-- правка в правиле ядра -->\n")
        with open(cls.x / "rules/forms.md", "a", encoding="utf-8") as fh:
            fh.write("\n<!-- правка в правиле оверлея -->\n")
        cls.x_status = subprocess.run(["git", "-C", str(cls.x), "status", "--porcelain", "--untracked-files=all"],
                                      capture_output=True).stdout
        install(cls.b, cls.p)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, onerror=_unlock)

    def cats(self):
        return {rel: i["category"] for rel, i in kun_split.inventory(self.x)["files"].items()}

    def test_1_inventory_classifies_by_content(self):
        c = self.cats()
        self.assertEqual(c["rules/delegation.md"], kun_split.BUILD_MODIFIED)
        self.assertEqual(c["rules/forms.md"], kun_split.INSTALLED_EDITED)
        self.assertEqual(c["rules/anti-patterns.md"], kun_split.INSTALLED)
        self.assertEqual(c[".kun/agents/explorer.md"], kun_split.INSTALLED)
        self.assertEqual(c["AGENTS.md"], kun_split.PROJECT)
        self.assertEqual(c[".dev.env"], kun_split.PROJECT)
        self.assertEqual(c["src/CommonModules/Демо/Ext/Module.bsl"], kun_split.PROJECT)
        self.assertEqual(c[".venv/Lib/site.txt"], kun_split.IGNORED_OTHER)
        self.assertEqual(c["ci/check.py"], kun_split.BUILD)

    def test_2_carry_refuses_without_decision_on_build_edits(self):
        self.assertEqual(run("carry", self.x, self.p)[0], 2)

    def test_3_carry_plan_writes_nothing(self):
        before = (self.p / "AGENTS.md").read_bytes()
        code, out = run("carry", self.x, self.p, "--with-build-edits")
        self.assertEqual(code, 0, out)
        self.assertEqual((self.p / "AGENTS.md").read_bytes(), before)
        self.assertFalse((self.p / ".dev.env").exists())

    def test_4_apply_verify_and_repeat(self):
        code, out = run("carry", self.x, self.p, "--with-build-edits", "--apply")
        self.assertEqual(code, 0, out)
        self.assertNotIn("НЕ СОВПАЛО", out)
        self.assertFalse((self.p / ".venv").exists())
        code, out = run("verify", self.p, self.b)
        self.assertEqual(code, 0, out)
        self.assertIn("rules/forms.md", out)
        code, out = run("carry", self.x, self.p, "--with-build-edits", "--apply")
        self.assertEqual(code, 0, out)
        self.assertNotIn("скопировать", out)
        status = subprocess.run(["git", "-C", str(self.x), "status", "--porcelain", "--untracked-files=all"],
                                capture_output=True).stdout
        self.assertEqual(status, self.x_status, "X изменился")

    def test_5_verify_rejects_combined_layout(self):
        self.assertEqual(run("verify", self.x, self.b)[0], 2)

    def test_6_verify_catches_broken_project(self):
        broken = self.tmp / "P-broken"
        shutil.copytree(self.p, broken)
        (broken / "rules/zz-orphan.md").write_text("x\n", encoding="utf-8")
        (broken / "AGENTS.md").write_text((broken / "AGENTS.md").read_text(encoding="utf-8") + "\n{{STACK}}\n",
                                         encoding="utf-8")
        (broken / ".kun/agents/tester.md").unlink()
        code, out = run("verify", broken, self.b)
        self.assertEqual(code, 1, out)
        for needle in ("zz-orphan.md", "STACK", "tester.md"):
            self.assertIn(needle, out)

    def test_7_conflict_is_not_overwritten(self):
        other = self.tmp / "P-conflict"
        shutil.copytree(self.p, other)
        target = other / "src/CommonModules/Демо/Ext/Module.bsl"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("чужое\n", encoding="utf-8")
        code, out = run("carry", self.x, other, "--skip-build-edits", "--apply")
        self.assertEqual(code, 1, out)
        self.assertEqual(target.read_text(encoding="utf-8"), "чужое\n")


if __name__ == "__main__":
    unittest.main(verbosity=1)
