#!/usr/bin/env python3
"""Adversarial regressions for Studio's explicit module dependency boundaries."""
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from studio_module_graph import MODULES, Module, validate_module_graph


class StudioModuleGraphTests(unittest.TestCase):
    def test_real_studio_module_graph_is_reviewed_and_ordered(self):
        shell = (ROOT / "web/studio-shell.html").read_text()
        self.assertEqual(validate_module_graph(shell, ROOT / "web"), MODULES)
        self.assertEqual(len(MODULES), 28)
        self.assertEqual(len({m.filename for m in MODULES}), len(MODULES))

    def test_missing_duplicate_unreviewed_and_reordered_slots_are_rejected(self):
        shell = (ROOT / "web/studio-shell.html").read_text()
        for bad in (
            shell.replace("/*STUDIO_MUSIC*/", "", 1),
            shell.replace("/*STUDIO_MUSIC*/", "/*STUDIO_MUSIC*//*STUDIO_MUSIC*/", 1),
            shell + "\n/*STUDIO_UNREGISTERED*/",
            shell.replace("/*STUDIO_MUSIC*/", "%%TEMP%%", 1).replace(
                "/*STUDIO_MUSIC_UI*/", "/*STUDIO_MUSIC*/", 1).replace(
                "%%TEMP%%", "/*STUDIO_MUSIC_UI*/", 1),
        ):
            with self.assertRaises(ValueError):
                validate_module_graph(bad, ROOT / "web")

    def test_invalid_dependency_graph_is_rejected_in_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            web = Path(tmp)
            (web / "core.js").write_text("root.NexusCore=Object.freeze({});")
            (web / "ui.js").write_text("root.NexusUI={run:()=>NexusCore.run};")
            shell = "/*STUDIO_THEME*/<script>/*STUDIO_CORE*/</script><script>/*STUDIO_UI*/</script>"
            core = Module("/*STUDIO_CORE*/", "core.js", "NexusCore")
            ui = Module("/*STUDIO_UI*/", "ui.js", "NexusUI", ("NexusCore",))
            self.assertEqual(validate_module_graph(shell, web, (core, ui)), (core, ui))

            variations = [
                (core, replace(ui, requires=())),
                (core, replace(ui, requires=("NexusCore", "NexusMissing"))),
                (replace(core, provides="NexusUI"), ui),
                (core, replace(ui, provides="NexusCore")),
                (core, replace(ui, filename="core.js")),
                (core, replace(ui, filename="../escape.js")),
                (core, replace(ui, deferred=("NexusUnknown",))),
            ]
            for modules in variations:
                with self.subTest(modules=modules), self.assertRaises(ValueError):
                    validate_module_graph(shell, web, modules)

            with self.assertRaises(ValueError):
                validate_module_graph(shell, web, (ui, core))

    def test_global_provider_ownership_and_new_cross_feature_coupling_are_guarded(self):
        with tempfile.TemporaryDirectory() as tmp:
            web = Path(tmp)
            (web / "core.js").write_text("root.NexusCore={};")
            (web / "ui.js").write_text("root.NexusUI={}; const newCoupling=NexusMusic;")
            shell = "/*STUDIO_THEME*//*STUDIO_CORE*//*STUDIO_UI*/"
            specs = (
                Module("/*STUDIO_CORE*/", "core.js", "NexusCore"),
                Module("/*STUDIO_UI*/", "ui.js", "NexusUI"),
            )
            with self.assertRaisesRegex(ValueError, "undeclared or obsolete"):
                validate_module_graph(shell, web, specs)
            (web / "ui.js").write_text("root.NexusUI={};root.NexusCore={};")
            with self.assertRaisesRegex(ValueError, "global export"):
                validate_module_graph(shell, web, specs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
