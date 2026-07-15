from rackhead_evaluator.errors import ValidationIssue, ValidationStage


def test_validation_issue_render_is_bounded() -> None:
    issue = ValidationIssue(
        code="RH-TEST-001",
        stage=ValidationStage.REFERENTIAL,
        message="bad value",
        path="tools[0]",
        value="x" * 500,
        suggestion="fix it",
    )
    rendered = issue.render()
    assert "RH-TEST-001" in rendered
    assert "..." in rendered
    assert len(rendered) < 400


def test_structural_issue_does_not_echo_arbitrary_string() -> None:
    issue = ValidationIssue(
        code="RH-TEST-002",
        stage=ValidationStage.STRUCTURAL,
        message="unknown field",
        path="workflow.api_key",
        value="secret-value-that-must-not-be-printed",
    )
    rendered = issue.render()
    assert "workflow.api_key" in rendered
    assert "secret-value" not in rendered
