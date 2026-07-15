"""Safe and fail-closed YAML parsing with normalized failures."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from yaml.constructor import ConstructorError
from yaml.events import AliasEvent
from yaml.nodes import MappingNode
from yaml.resolver import BaseResolver

from rackhead_evaluator.errors import ValidationIssue, ValidationStage, fail

MAX_INPUT_BYTES = 1_048_576


class StrictSafeLoader(yaml.SafeLoader):
    """SafeLoader that rejects aliases and ambiguous duplicate mapping keys."""

    def compose_node(self, parent: Any, index: Any) -> Any:
        if self.check_event(AliasEvent):  # type: ignore[no-untyped-call]
            event = self.peek_event()  # type: ignore[no-untyped-call]
            raise ConstructorError(
                "while composing YAML",
                getattr(event, "start_mark", None),
                "YAML aliases are not supported in workflow schema 0.1",
                getattr(event, "start_mark", None),
            )
        return super().compose_node(parent, index)


def _construct_unique_mapping(
    loader: StrictSafeLoader,
    node: MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


StrictSafeLoader.add_constructor(
    BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def read_yaml_mapping(path: Path, *, subject: str) -> dict[str, Any]:
    """Read bounded UTF-8 YAML and require a unique-key mapping root."""

    try:
        with path.open("rb") as stream:
            raw_bytes = stream.read(MAX_INPUT_BYTES + 1)
    except FileNotFoundError:
        fail(
            ValidationIssue(
                code="RH-CONFIG-001",
                stage=ValidationStage.CONFIGURATION,
                message=f"{subject} file does not exist",
                path=str(path),
                suggestion="provide a readable UTF-8 YAML file",
            )
        )
    except OSError:
        fail(
            ValidationIssue(
                code="RH-CONFIG-002",
                stage=ValidationStage.CONFIGURATION,
                message=f"{subject} file could not be read",
                path=str(path),
                suggestion="check file permissions and file type",
            )
        )

    if len(raw_bytes) > MAX_INPUT_BYTES:
        fail(
            ValidationIssue(
                code="RH-CONFIG-003",
                stage=ValidationStage.CONFIGURATION,
                message=f"{subject} file exceeds the v0.1 input size limit",
                path=str(path),
                value=len(raw_bytes),
                suggestion=f"reduce the file to at most {MAX_INPUT_BYTES} bytes",
            )
        )

    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        fail(
            ValidationIssue(
                code="RH-CONFIG-004",
                stage=ValidationStage.CONFIGURATION,
                message=f"{subject} file is not valid UTF-8",
                path=str(path),
                suggestion="save the YAML document using UTF-8 encoding",
            )
        )

    try:
        loaded = yaml.load(text, Loader=StrictSafeLoader)
    except (yaml.YAMLError, RecursionError) as exc:
        marker = getattr(exc, "problem_mark", None)
        location = str(path)
        if marker is not None:
            location = f"{path}:{marker.line + 1}:{marker.column + 1}"
        fail(
            ValidationIssue(
                code="RH-SCHEMA-STRUCT-001",
                stage=ValidationStage.STRUCTURAL,
                message=f"malformed, ambiguous, or unsafe YAML in {subject} file",
                path=location,
                suggestion=(
                    "fix YAML syntax, remove duplicate keys and aliases, "
                    "and use only standard safe YAML values"
                ),
            )
        )

    if not isinstance(loaded, dict):
        fail(
            ValidationIssue(
                code="RH-SCHEMA-STRUCT-002",
                stage=ValidationStage.STRUCTURAL,
                message=f"{subject} root must be a mapping",
                path="$",
                value=type(loaded).__name__,
                suggestion="use key-value fields at the YAML document root",
            )
        )
    return loaded
