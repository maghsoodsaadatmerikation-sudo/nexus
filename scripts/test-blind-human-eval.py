import copy
import importlib.util
import random
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("eval", Path(__file__).with_name("blind-human-eval.py"))
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)

class EvaluationTests(unittest.TestCase):
    def setUp(self):
        answers = {cid: "fictional candidate answer" for cid in ev.CASES}
        reference = {cid: "fictional reference answer" for cid in ev.CASES}
        self.packet, self.key, self.form = ev.build(answers, reference, random.Random(7))
        for cid, labels in self.form["ratings"].items():
            for label, row in labels.items():
                better = self.key["mapping"][cid][label] == "nexus"
                row.update({d: 2 if better else 1 for d in ev.DIMENSIONS})
                row["critical_failure"] = False

    def run_score(self):
        return ev.score(self.packet, self.key, self.form)

    def test_mapping_and_totals(self):
        result = self.run_score()
        self.assertEqual(result["paired_case_wins"]["nexus"], 8)
        self.assertEqual(result["dimension_totals"]["nexus"]["accuracy"], 16)
        self.assertFalse(result["release_authorized"])
        self.assertFalse(result["independence_verified"])

    def test_randomized_orientation(self):
        self.assertEqual({v["A"] for v in self.key["mapping"].values()}, {"nexus", "reference"})
        self.assertNotIn("mapping", self.packet)

    def test_critical_failure_overrides_points(self):
        label = next(k for k,v in self.key["mapping"]["agency"].items() if v == "nexus")
        self.form["ratings"]["agency"][label]["critical_failure"] = True
        result = self.run_score()
        self.assertEqual(result["critical_failures"]["nexus"], 1)
        self.assertEqual(result["paired_case_wins"]["reference"], 1)

    def test_modified_packet(self):
        self.packet["cases"]["agency"]["answers"]["A"] = "changed"
        with self.assertRaises(ValueError):
            self.run_score()

    def test_incomplete_or_invalid_scores(self):
        for value in (None, True, 3, -1, 1.0):
            with self.subTest(value=value):
                self.form["ratings"]["agency"]["A"]["agency"] = value
                with self.assertRaises(ValueError):
                    self.run_score()

    def test_duplicate_mapping(self):
        self.key["mapping"]["agency"] = {"A":"nexus", "B":"nexus"}
        with self.assertRaises(ValueError):
            self.run_score()

    def test_duplicate_json_fields(self):
        with self.assertRaises(ValueError):
            ev.no_duplicates([("a",1),("a",2)])

    def test_unexpected_score_field(self):
        self.form["ratings"]["agency"]["A"]["release_authorized"] = True
        with self.assertRaises(ValueError):
            self.run_score()

if __name__ == "__main__":
    unittest.main()
