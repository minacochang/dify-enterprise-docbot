"""values_diff モジュールのユニットテスト"""
import unittest
from unittest.mock import MagicMock

from docbot.values_diff import (
    flatten_values,
    compute_diff,
    compute_user_impacts,
    run_helm_show_values,
    build_values_diff_result,
    ARRAY_MODE_SET,
    ARRAY_MODE_INDEX,
)


class TestFlatten(unittest.TestCase):
    def test_flatten_set_scalar(self):
        data = {"a": 1, "b": "x"}
        flat = flatten_values(data, ARRAY_MODE_SET)
        self.assertEqual(flat["a"], ("int", 1))
        self.assertEqual(flat["b"], ("str", "x"))

    def test_flatten_set_nested(self):
        data = {"a": {"b": {"c": 42}}}
        flat = flatten_values(data, ARRAY_MODE_SET)
        self.assertEqual(flat["a.b.c"], ("int", 42))

    def test_flatten_set_list(self):
        data = {"x": [{"k": 1}, {"k": 2}]}
        flat = flatten_values(data, ARRAY_MODE_SET)
        self.assertIn("x", flat)
        self.assertEqual(flat["x"][0], "list")
        self.assertIn("x[].k", flat)
        self.assertEqual(flat["x[].k"], ("int", 2))

    def test_flatten_index_list(self):
        data = {"x": [{"k": 1}, {"k": 2}]}
        flat = flatten_values(data, ARRAY_MODE_INDEX)
        self.assertEqual(flat["x[0].k"], ("int", 1))
        self.assertEqual(flat["x[1].k"], ("int", 2))


class TestComputeDiff(unittest.TestCase):
    def test_added_removed_type_changed_default_changed(self):
        from_yaml = """
a: 1
b: "old"
c: true
d: {"x": 1}
"""
        to_yaml = """
a: 1
b: "new"
c: "str"
e: 100
"""
        import yaml

        from_data = yaml.safe_load(from_yaml) or {}
        to_data = yaml.safe_load(to_yaml) or {}
        from_flat = flatten_values(from_data, ARRAY_MODE_SET)
        to_flat = flatten_values(to_data, ARRAY_MODE_SET)
        diff = compute_diff(from_flat, to_flat)

        self.assertEqual(len(diff["added"]), 1)
        self.assertEqual(diff["added"][0]["path"], "e")

        self.assertEqual(len(diff["removed"]), 1)
        self.assertEqual(diff["removed"][0]["path"], "d.x")

        self.assertEqual(len(diff["type_changed"]), 1)
        self.assertEqual(diff["type_changed"][0]["path"], "c")
        self.assertEqual(diff["type_changed"][0]["from_type"], "bool")
        self.assertEqual(diff["type_changed"][0]["to_type"], "str")

        self.assertEqual(len(diff["default_changed"]), 1)
        self.assertEqual(diff["default_changed"][0]["path"], "b")


class TestUserImpacts(unittest.TestCase):
    def test_removed_but_used(self):
        from_yaml = "removed_key: 42"
        to_yaml = ""
        user_yaml = "removed_key: 99"

        result = build_values_diff_result(
            "ch/art", None, "ch/art", None,
            from_yaml, to_yaml or "{}", user_yaml,
            ARRAY_MODE_SET,
        )
        self.assertNotIn("error", result)
        self.assertEqual(result["summary"]["user_impacts"], 1)
        self.assertEqual(result["user_impacts"][0]["kind"], "removed_but_used")
        self.assertEqual(result["user_impacts"][0]["path"], "removed_key")
        self.assertEqual(result["user_impacts"][0]["user_value"], 99)

    def test_type_changed_and_used(self):
        from_yaml = "key: 123"
        to_yaml = "key: \"string\""
        user_yaml = "key: 456"

        result = build_values_diff_result(
            "ch/art", None, "ch/art", None,
            from_yaml, to_yaml, user_yaml,
            ARRAY_MODE_SET,
        )
        self.assertNotIn("error", result)
        impacts = [i for i in result["user_impacts"] if i["kind"] == "type_changed_and_used"]
        self.assertEqual(len(impacts), 1)
        self.assertEqual(impacts[0]["path"], "key")
        self.assertEqual(impacts[0]["from_type"], "int")
        self.assertEqual(impacts[0]["to_type"], "str")


class TestRunHelmShowValues(unittest.TestCase):
    def test_helm_not_found(self):
        def mock_run(*args, **kwargs):
            raise FileNotFoundError("helm")

        _, err = run_helm_show_values("dify/dify", None, run_subprocess=mock_run)
        self.assertIn("helm", err)
        self.assertIn("見つかりません", err)

    def test_helm_success(self):
        def mock_run(cmd, **kwargs):
            m = MagicMock()
            m.returncode = 0
            m.stdout = "a: 1"
            m.stderr = ""
            return m

        out, err = run_helm_show_values("dify/dify", "0.14.0", run_subprocess=mock_run)
        self.assertIsNone(err)
        self.assertEqual(out, "a: 1")

    def test_helm_failure(self):
        def mock_run(cmd, **kwargs):
            m = MagicMock()
            m.returncode = 1
            m.stdout = ""
            m.stderr = "chart not found"
            return m

        out, err = run_helm_show_values("bad/chart", None, run_subprocess=mock_run)
        self.assertIsNone(out)
        self.assertIn("chart not found", err)
