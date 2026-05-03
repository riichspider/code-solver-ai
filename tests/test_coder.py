from core.coder import CodeGenerator


class RetryClient:
    def __init__(self):
        self.calls = 0

    def generate_json(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return {
                "filename": "solution.js",
                "code": "",
                "test_filename": "test_solution.js",
                "tests": "",
                "explanation": [],
                "notes": [],
            }
        return {
            "filename": "solution.js",
            "code": "```javascript\nfunction sum(a, b) {\\n  return a + b;\\n}\n```",
            "test_filename": "test_solution.js",
            "tests": "```javascript\nconst assert = require('assert');\\nassert.equal(sum(2, 3), 5);\\n```",
            "explanation": ["Works after retry."],
            "notes": [],
        }


class BrokenRepairClient:
    @staticmethod
    def generate_json(**kwargs):
        raise RuntimeError("bad response")


def test_code_generator_retries_and_normalizes_multiline_output():
    generator = CodeGenerator(client=RetryClient())

    result = generator.generate(
        problem="Create a sum helper",
        classification="enhancement",
        language="javascript",
        understanding="Create a tiny helper",
        plan_steps=["Write the helper", "Add a small assertion"],
        constraints=["Use no external dependencies"],
        risks=["Bad formatting from the model"],
        success_criteria=["The code is runnable"],
        context_text="",
        similar_context=[],
        model="fake-model",
        mode="fast",
        options={},
    )

    assert "function sum" in result["code"]
    assert "\\n" not in result["code"]
    assert "assert.equal" in result["tests"]


def test_code_generator_repair_returns_previous_solution_on_failure():
    generator = CodeGenerator(client=BrokenRepairClient())
    previous_solution = {
        "filename": "solution.py",
        "test_filename": "test_solution.py",
        "code": "def add(a, b):\n    return a + b\n",
        "tests": "",
        "explanation": ["Existing solution."],
        "notes": [],
    }

    repaired = generator.repair(
        problem="Repair the helper",
        language="python",
        previous_solution=previous_solution,
        validation={"status": "failed"},
        model="fake-model",
        options={},
    )

    assert repaired == previous_solution
