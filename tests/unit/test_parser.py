from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from rackhead_evaluator.errors import ValidationFailure
from rackhead_evaluator.parser import MAX_INPUT_BYTES, read_yaml_mapping


def test_malformed_yaml_is_controlled(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("tools: [\n", encoding="utf-8")
    with pytest.raises(ValidationFailure) as caught:
        read_yaml_mapping(path, subject="workflow")
    assert caught.value.issues[0].code == "RH-SCHEMA-STRUCT-001"


def test_unsafe_yaml_constructor_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "unsafe.yaml"
    path.write_text(
        "payload: !!python/object/apply:os.system ['echo unsafe']\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationFailure) as caught:
        read_yaml_mapping(path, subject="workflow")
    assert caught.value.issues[0].code == "RH-SCHEMA-STRUCT-001"


def test_yaml_root_must_be_mapping(tmp_path: Path) -> None:
    path = tmp_path / "list.yaml"
    path.write_text("- one\n- two\n", encoding="utf-8")
    with pytest.raises(ValidationFailure) as caught:
        read_yaml_mapping(path, subject="workflow")
    assert caught.value.issues[0].code == "RH-SCHEMA-STRUCT-002"


def test_missing_file_is_configuration_error(tmp_path: Path) -> None:
    with pytest.raises(ValidationFailure) as caught:
        read_yaml_mapping(tmp_path / "missing.yaml", subject="workflow")
    assert caught.value.issues[0].code == "RH-CONFIG-001"


def test_yaml_alias_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "alias.yaml"
    path.write_text("base: &base {value: 1}\ncopy: *base\n", encoding="utf-8")
    with pytest.raises(ValidationFailure) as caught:
        read_yaml_mapping(path, subject="workflow")
    assert caught.value.issues[0].code == "RH-SCHEMA-STRUCT-001"


def test_duplicate_mapping_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.yaml"
    path.write_text('schema_version: "0.1"\nschema_version: "0.2"\n', encoding="utf-8")
    with pytest.raises(ValidationFailure) as caught:
        read_yaml_mapping(path, subject="workflow")
    assert caught.value.issues[0].code == "RH-SCHEMA-STRUCT-001"


def test_oversized_file_is_rejected_before_parsing(tmp_path: Path) -> None:
    path = tmp_path / "large.yaml"
    path.write_bytes(b"x" * 1_048_577)
    with pytest.raises(ValidationFailure) as caught:
        read_yaml_mapping(path, subject="workflow")
    assert caught.value.issues[0].code == "RH-CONFIG-003"


def test_non_utf8_file_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "binary.yaml"
    path.write_bytes(b"\xff\xfe")
    with pytest.raises(ValidationFailure) as caught:
        read_yaml_mapping(path, subject="workflow")
    assert caught.value.issues[0].code == "RH-CONFIG-004"


def test_reader_is_bounded_before_size_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_sizes: list[int] = []

    class TrackingReader(BytesIO):
        def read(self, size: int = -1) -> bytes:
            requested_sizes.append(size)
            return super().read(size)

    stream = TrackingReader(b"x" * (MAX_INPUT_BYTES + 1))
    monkeypatch.setattr(Path, "open", lambda *args, **kwargs: stream)

    with pytest.raises(ValidationFailure) as caught:
        read_yaml_mapping(Path("synthetic.yaml"), subject="workflow")

    assert requested_sizes == [MAX_INPUT_BYTES + 1]
    assert caught.value.issues[0].code == "RH-CONFIG-003"


def test_deeply_nested_yaml_is_controlled(tmp_path: Path) -> None:
    path = tmp_path / "deep.yaml"
    path.write_text("value: " + "[" * 2000 + "0" + "]" * 2000, encoding="utf-8")

    with pytest.raises(ValidationFailure) as caught:
        read_yaml_mapping(path, subject="workflow")

    assert caught.value.issues[0].code == "RH-SCHEMA-STRUCT-001"
