from utils.markdown import render_solution_markdown
from tests.test_helpers import create_mock_solution_result


def test_render_solution_markdown_contains_expected_sections():
    mock_result = create_mock_solution_result()
    markdown = render_solution_markdown(mock_result)

    assert "## 7. Generated Code" in markdown
    assert "## 9. Validation" in markdown
    assert "```python" in markdown
