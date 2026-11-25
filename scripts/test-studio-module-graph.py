#!/usr/bin/env python3
"""Adversarial regressions for Studio's explicit module dependency boundaries."""
from dataclasses import replace
from pathlib import Path
import os
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from studio_module_graph import (MODULES, Module, validate_executable_slots,
                                 validate_module_graph)


class StudioModuleGraphTests(unittest.TestCase):
    def test_real_studio_module_graph_is_reviewed_and_ordered(self):
        shell = (ROOT / "web/studio-shell.html").read_text()
        self.assertEqual(validate_module_graph(shell, ROOT / "web"), MODULES)
        self.assertEqual(len(MODULES), 29)
        self.assertEqual(len({m.filename for m in MODULES}), len(MODULES))

    def test_real_shell_has_plain_executable_slots(self):
        shell = (ROOT / "web/studio-shell.html").read_text()
        validate_executable_slots(shell, MODULES)

    def test_module_slots_cannot_be_moved_into_inert_markup(self):
        module = Module("/*STUDIO_ONE*/", "one.js")
        plain = "<script>/*STUDIO_ONE*/</script>"
        validate_executable_slots(plain, (module,))
        for bad in (
            "<!--" + plain + "-->",
            "<template>" + plain + "</template>",
            "<noscript>" + plain + "</noscript>",
            "<textarea>" + plain + "</textarea>",
            "<iframe>" + plain + "</iframe>",
            "<svg>" + plain + "</svg>",
            '<script type="application/json">/*STUDIO_ONE*/</script>',
            '<script defer>/*STUDIO_ONE*/</script>',
            '<script src="other.js">/*STUDIO_ONE*/</script>',
            '<div data-slot="/*STUDIO_ONE*/"></div>',
            "<script>const marker = '/*STUDIO_ONE*/';</script>",
            "<script>/*STUDIO_ONE*/",
            "<script/>/*STUDIO_ONE*/</script>",
        ):
            with self.subTest(shell=bad), self.assertRaises(ValueError):
                validate_executable_slots(bad, (module,))

    def test_script_slot_order_is_execution_order(self):
        first = Module("/*STUDIO_ONE*/", "one.js")
        second = Module("/*STUDIO_TWO*/", "two.js")
        a = "<script>/*STUDIO_ONE*/</script>"
        b = "<script>/*STUDIO_TWO*/</script>"
        validate_executable_slots(a + b, (first, second))
        for bad in (b + a, a + a + b, a):
            with self.subTest(shell=bad), self.assertRaises(ValueError):
                validate_executable_slots(bad, (first, second))

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

    def test_noncanonical_and_aliased_module_sources_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            web = Path(tmp)
            (web / "vendor").mkdir()
            (web / "vendor" / "one.js").write_text("const one=1;")
            shell = "/*STUDIO_THEME*//*STUDIO_ONE*//*STUDIO_TWO*/"
            first = Module("/*STUDIO_ONE*/", "vendor/one.js")
            second = Module("/*STUDIO_TWO*/", "two.js")
            (web / "two.js").write_text("const two=2;")
            self.assertEqual(validate_module_graph(shell, web, (first, second)),
                             (first, second))
            for invalid in ("vendor//one.js", "vendor/./one.js", "./two.js", "two.txt"):
                with self.subTest(path=invalid), self.assertRaises(ValueError):
                    validate_module_graph(shell, web, (first, replace(second, filename=invalid)))
            (web / "two.js").unlink()
            (web / "two.js").symlink_to(web / "vendor" / "one.js")
            with self.assertRaisesRegex(ValueError, "symlinked"):
                validate_module_graph(shell, web, (first, second))
            (web / "two.js").unlink()
            os.link(web / "vendor" / "one.js", web / "two.js")
            with self.assertRaisesRegex(ValueError, "aliased"):
                validate_module_graph(shell, web, (first, second))
            (web / "two.js").unlink()
            (web / "alias").symlink_to(web / "vendor", target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlinked"):
                validate_module_graph(shell, web,
                                      (first, replace(second, filename="alias/one.js")))

    def test_module_cannot_reintroduce_reserved_template_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            web = Path(tmp)
            module = Module("/*STUDIO_ONE*/", "one.js")
            shell = "/*STUDIO_THEME*//*STUDIO_ONE*/"
            (web / "one.js").write_text("const one=1; /*STUDIO_ONE*/")
            with self.assertRaisesRegex(ValueError, "reserved Studio template marker"):
                validate_module_graph(shell, web, (module,))
            (web / "one.js").write_text("const one=1;")
            with self.assertRaisesRegex(ValueError, "invalid Studio module"):
                validate_module_graph("/*STUDIO_THEME*/", web,
                                      (replace(module, marker="/*STUDIO_THEME*/"),))

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
