"""Validation-only CLI skeleton for Slice 1."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from rackhead_evaluator.errors import ValidationFailure
from rackhead_evaluator.validation import load_policy, load_workflow

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Validate a declared agent workflow against schema 0.1.",
)


@app.command()
def validate(
    workflow_path: Annotated[
        Path,
        typer.Argument(exists=False, dir_okay=False, readable=False),
    ],
    policy: Annotated[
        Path | None,
        typer.Option(
            "--policy",
            dir_okay=False,
            readable=False,
            help="Optional policy YAML to validate.",
        ),
    ] = None,
) -> None:
    """Validate one workflow without running security rules or generating reports."""

    try:
        workflow = load_workflow(workflow_path)
        if policy is not None:
            load_policy(policy)
    except ValidationFailure as exc:
        for issue in exc.issues:
            typer.echo(issue.render(), err=True)
        raise typer.Exit(code=2) from None
    except Exception:
        typer.echo(
            "RH-EVALUATOR-INTERNAL-001: unexpected internal evaluator failure",
            err=True,
        )
        raise typer.Exit(code=3) from None

    typer.echo(f"valid: {workflow.workflow.id} (schema {workflow.schema_version})")


if __name__ == "__main__":
    app()
