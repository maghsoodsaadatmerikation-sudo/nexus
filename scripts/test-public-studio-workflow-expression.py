#!/usr/bin/env python3
"""Regression guard for the exact Public Studio GitHub Actions job condition.

The original bug was a missing closing parenthesis in jobs.public-browser.if:
GitHub recorded a 0-job workflow failure before any Studio test ran.
No external YAML package or network access is required.
"""
from pathlib import Path
import unittest

WORKFLOW = Path(".github/workflows/studio-static-public.yml")
EXPECTED = (
    "github.event_name == 'workflow_dispatch' || "
    "contains(github.event.head_commit.message, '[verify-studio-public]') || "
    "(github.event_name == 'pull_request' && "
    "contains(github.event.pull_request.title, '[verify-studio-public]'))"
)


class WorkflowSyntaxError(ValueError):
    pass


def validate_expression(expression: str) -> None:
    if not expression.strip():
        raise WorkflowSyntaxError("missing condition")
    stack = []
    quoted = False
    i = 0
    while i < len(expression):
        char = expression[i]
        if char == "'":
            if quoted and i + 1 < len(expression) and expression[i + 1] == "'":
                i += 2
                continue
            quoted = not quoted
        elif not quoted:
            if char in "([{":
                stack.append(char)
            elif char in ")]}":
                match = {")": "(", "]": "[", "}": "{"}[char]
                if not stack or stack.pop() != match:
                    raise WorkflowSyntaxError("unmatched closing delimiter")
        i += 1
    if quoted or stack:
        raise WorkflowSyntaxError("unterminated quote or missing closing delimiter")


def inspect(source: str) -> None:
    # Only this job's job-level if is reviewed here; other workflow rules
    # remain protected by the repository-wide authority boundary validator.
    if "\t" in source:
        raise WorkflowSyntaxError("tab in workflow")
    lines = source.splitlines()
    jobs = [i for i, line in enumerate(lines) if line == "  public-browser:"]
    if len(jobs) != 1:
        raise WorkflowSyntaxError("missing/duplicate public-browser job")
    tail = lines[jobs[0] + 1:]
    stop = next((i for i, line in enumerate(tail)
                 if line.startswith("  ") and not line.startswith("    ") and line.strip()), len(tail))
    job = tail[:stop]
    conditions = [line.split("if:", 1)[1].strip()
                  for line in job if line.startswith("    if:")]
    if len(conditions) != 1:
        raise WorkflowSyntaxError("job-level if must be one explicit line")
    validate_expression(conditions[0])
    if conditions[0] != EXPECTED:
        raise WorkflowSyntaxError("public browser must remain manual or explicitly opted in")
    if "permissions:\n  contents: read" not in source:
        raise WorkflowSyntaxError("read-only global contents missing")
    if "pull_request_target:" in source:
        raise WorkflowSyntaxError("privileged PR event prohibited")
    if "    permissions:\n      contents: read" not in source:
        raise WorkflowSyntaxError("read-only job contents missing")


class PublicStudioExpressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = WORKFLOW.read_text(encoding="utf-8")

    def test_committed_workflow_condition_is_parseable_and_canonical(self):
        inspect(self.original)

    def test_missing_final_closing_parenthesis_is_rejected(self):
        before = EXPECTED[:-1]
        with self.assertRaises(WorkflowSyntaxError):
            inspect(self.original.replace(EXPECTED, before))

    def test_extra_closing_parenthesis_is_rejected(self):
        with self.assertRaises(WorkflowSyntaxError):
            inspect(self.original.replace(EXPECTED, EXPECTED + ")"))

    def test_unterminated_quote_is_rejected(self):
        with self.assertRaises(WorkflowSyntaxError):
            inspect(self.original.replace(EXPECTED, EXPECTED + "'"))

    def test_quoted_parentheses_are_not_counted(self):
        validate_expression("contains(github.ref, '[main])')")

    def test_escaped_quotes_do_not_confuse_parser(self):
        validate_expression("contains(github.ref, 'a''(b')")

    def test_change_to_unconditional_browser_job_is_rejected(self):
        with self.assertRaises(WorkflowSyntaxError):
            inspect(self.original.replace(EXPECTED, "always()"))

    def test_conditional_job_cannot_be_duplicated(self):
        with self.assertRaises(WorkflowSyntaxError):
            inspect(self.original.replace("  public-browser:", "  public-browser:\n  public-browser:"))

    def test_missing_or_duplicate_condition_fails_closed(self):
        with self.assertRaises(WorkflowSyntaxError):
            inspect(self.original.replace("    if: " + EXPECTED, "    name: absent-condition"))
        with self.assertRaises(WorkflowSyntaxError):
            inspect(self.original.replace("    if: " + EXPECTED,
                                          "    if: " + EXPECTED + "\n    if: " + EXPECTED))

    def test_workflow_must_remain_read_only(self):
        with self.assertRaises(WorkflowSyntaxError):
            inspect(self.original.replace("permissions:\n  contents: read",
                                          "permissions:\n  contents: write", 1))
        with self.assertRaises(WorkflowSyntaxError):
            inspect(self.original.replace("    permissions:\n      contents: read",
                                          "    permissions:\n      contents: write"))

    def test_privileged_pr_event_is_rejected(self):
        with self.assertRaises(WorkflowSyntaxError):
            inspect(self.original.replace("  pull_request:", "  pull_request_target:", 1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
