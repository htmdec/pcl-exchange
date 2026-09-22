from datetime import datetime, timezone
import json
import re
from typing import Any, Callable, Dict, Optional

import pytest

from pcl_exchange.builder import PCLMessageBuilder, build_ack, build_nack
from pcl_exchange.crypto import Signer
from pcl_exchange.models import (
    DEFAULT_SCHEMAS,
    PCLCancelJobContent,
    PCLEnvelope,
    PCLError,
    PCLErrorCode,
    PCLErrorFault,
    PCLLaunchWorkflowContent,
    PCLMeasurementRequestContent,
    PCLRegisterDataContent,
    PCLUpdateMetadataContent,
)
from pcl_exchange.validation import validate_structure


def _measurement_payload(valid_payload_data: Dict[str, Any]) -> PCLMeasurementRequestContent:
    return PCLMeasurementRequestContent.create(
        instrument_ref={"@id": valid_payload_data["instrument"]},
        sample_ref={"@id": valid_payload_data["sample"]},
        method_ref={"@id": valid_payload_data["method"]},
        params=valid_payload_data["params"],
    )


def _request_metadata(
    request_envelope_metadata: Dict[str, Any], **overrides: Any
) -> Dict[str, Any]:
    metadata = dict(request_envelope_metadata)
    metadata.update(overrides)
    return metadata


def test_register_data_content_helper_serializes_expected_fields() -> None:
    payload = PCLRegisterDataContent.create(
        name="XRD Run 42 Results",
        identifier="doi:10.5072/dataset.0001",
        project_ref={"identifier": "doi:10.5072/project.0001"},
        sample_ref={"identifier": "igsn:JHABOX00000"},
        attributed_to_ref={"@id": "https://ror.org/0sndfake1"},
        distribution={
            "@type": "DataDownload",
            "contentUrl": {"@id": "https://example.org/data/run-42.zip"},
            "encodingFormat": "application/zip",
            "sha256": "a" * 64,
        },
        generated_at_time="2026-01-01T00:00:00Z",
    )

    data = payload.model_dump(mode="json", by_alias=True, exclude_none=True)

    assert data["@type"] == "Dataset"
    assert data["isPartOf"]["identifier"] == "doi:10.5072/project.0001"
    assert data["about"]["identifier"] == "igsn:JHABOX00000"
    assert data["prov:wasAttributedTo"]["@id"] == "https://ror.org/0sndfake1"


def test_launch_workflow_content_helper_serializes_expected_fields() -> None:
    payload = PCLLaunchWorkflowContent.create(
        name="My Workflow",
        programming_language="CWL v1.2",
        params={"scan_range": {"val": "10 90"}},
        code_repository_ref={"@id": "https://example.org/workflows/main"},
    )

    data = payload.model_dump(mode="json", by_alias=True, exclude_none=True)

    assert data["@type"] == "SoftwareSourceCode"
    assert data["programmingLanguage"] == "CWL v1.2"
    assert data["codeRepository"]["@id"] == "https://example.org/workflows/main"
    assert data["parameter"][0]["name"] == "scan_range"


def test_update_metadata_content_helper_serializes_expected_fields() -> None:
    payload = PCLUpdateMetadataContent.create(
        object_ref={"@id": "https://example.org/datasets/42"},
        attributed_to_ref={"@id": "https://ror.org/0sndfake1"},
        updates={"description": "Updated description"},
    )

    data = payload.model_dump(mode="json", by_alias=True, exclude_none=True)

    assert data["@type"] == "UpdateAction"
    assert data["object"]["@id"] == "https://example.org/datasets/42"
    assert data["prov:wasAttributedTo"]["@id"] == "https://ror.org/0sndfake1"
    assert data["parameter"][0]["name"] == "description"


def test_cancel_job_content_helper_serializes_expected_fields() -> None:
    payload = PCLCancelJobContent.create(
        correlation_id="pcl-req-00042",
        attributed_to_ref={"@id": "https://ror.org/0sndfake1"},
        description="Cancel duplicate request",
    )

    data = payload.model_dump(mode="json", by_alias=True, exclude_none=True)

    assert data["@type"] == "Action"
    assert data["object"]["@type"] == "PropertyValue"
    assert data["object"]["name"] == "correlationId"
    assert data["object"]["value"] == "pcl-req-00042"


def test_builder_accepts_register_data_payload(
    builder_defaults: Dict[str, str],
    request_envelope_metadata: Dict[str, Any],
) -> None:
    builder = PCLMessageBuilder(
        sender_id=builder_defaults["sender_id"],
        receiver_id=builder_defaults["receiver_id"],
        action_type="register_data",
    )
    builder.set_payload(
        PCLRegisterDataContent.create(
            name="XRD Run 42 Results",
            identifier="doi:10.5072/dataset.0001",
            project_ref={"identifier": request_envelope_metadata["project"]},
            sample_ref={"identifier": request_envelope_metadata["sample"]},
            attributed_to_ref={"@id": builder_defaults["sender_id"]},
            distribution={
                "@type": "DataDownload",
                "contentUrl": {"@id": "https://example.org/data/run-42.zip"},
                "encodingFormat": "application/zip",
                "sha256": "a" * 64,
            },
        )
    )
    builder.set_envelope_metadata(**_request_metadata(request_envelope_metadata, capabilities=["data.register"]))

    message = builder.build().model_dump(mode="json", by_alias=True)
    content_node = next(item for item in message["@graph"] if item.get("@id") == "#content")
    envelope_node = next(item for item in message["@graph"] if item.get("@id") == "#envelope")

    assert content_node["@type"] == "Dataset"
    assert envelope_node["action"] == "register_data"


def test_builder_initialization(builder_defaults: Dict[str, str]) -> None:
    builder = PCLMessageBuilder(**builder_defaults)
    assert builder.sender == builder_defaults["sender_id"]
    assert builder.receiver == builder_defaults["receiver_id"]
    assert builder.action_type == builder_defaults["action_type"]
    assert builder.schema_uri == DEFAULT_SCHEMAS[builder_defaults["action_type"]]


def test_builder_init_invalid_action_raises_value_error(builder_defaults: Dict[str, str]) -> None:
    with pytest.raises(ValueError, match="Unsupported action type"):
        PCLMessageBuilder(
            sender_id=builder_defaults["sender_id"],
            receiver_id=builder_defaults["receiver_id"],
            action_type="unsupported_action",
        )


def test_builder_action_type_locks_schema_default(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
    request_envelope_metadata: Dict[str, Any],
) -> None:
    builder = PCLMessageBuilder(
        sender_id=builder_defaults["sender_id"],
        receiver_id=builder_defaults["receiver_id"],
        action_type="launch_workflow",
    )
    builder.set_payload(_measurement_payload(valid_payload_data))
    builder.set_envelope_metadata(**_request_metadata(request_envelope_metadata))

    envelope = next(
        item
        for item in builder.build().model_dump(by_alias=True, mode="json")["@graph"]
        if item["@id"] == "#envelope"
    )

    assert envelope["action"] == "launch_workflow"
    assert envelope["schema"] == DEFAULT_SCHEMAS["launch_workflow"]


def test_build_minimal_message(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
    request_envelope_metadata: Dict[str, Any],
) -> None:
    """Test creating a message and checking critical JSON-LD fields."""
    builder = PCLMessageBuilder(**builder_defaults)

    builder.set_payload(_measurement_payload(valid_payload_data))
    builder.set_envelope_metadata(**_request_metadata(request_envelope_metadata))
    message = builder.build()
    json_output = message.model_dump(by_alias=True, mode="json")

    assert "@context" in json_output
    assert "@graph" in json_output

    graph = json_output["@graph"]
    envelope = next(item for item in graph if item["@id"] == "#envelope")

    assert envelope["sender"] == builder_defaults["sender_id"]
    assert "xrd.powder.theta-2theta" in envelope["capabilities"]
    assert envelope["action"] == "request_measurement"
    assert envelope["schema"] == DEFAULT_SCHEMAS["request_measurement"]


def test_missing_content_raises_error(builder_defaults: Dict[str, str]) -> None:
    """Trying to build without setting content should fail."""
    builder = PCLMessageBuilder(**builder_defaults)

    with pytest.raises(ValueError, match="Message payload has not been set"):
        builder.build()


def test_builder_sets_routing_fields(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
    request_envelope_metadata: Dict[str, Any],
) -> None:
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_payload(_measurement_payload(valid_payload_data))

    deadline = datetime(2030, 1, 1, tzinfo=timezone.utc)

    builder.set_envelope_metadata(
        **_request_metadata(
            request_envelope_metadata,
            respond_to="https://example.org/hooks/status",
            correlation_id="pcl-req-00042",
            idempotency_key="pcl-req-00042-v1",
            ttl="PT10M",
            deadline=deadline,
            priority=5,
            protocol_version="1.1",
        )
    )

    message = builder.build()
    json_output = message.model_dump(by_alias=True, mode="json")
    envelope = next(item for item in json_output["@graph"] if item["@id"] == "#envelope")

    assert envelope["respondTo"] == "https://example.org/hooks/status"
    assert envelope["correlationId"] == "pcl-req-00042"
    assert envelope["idempotencyKey"] == "pcl-req-00042-v1"
    assert envelope["ttl"] == "PT10M"
    assert envelope["deadline"] == deadline.isoformat().replace("+00:00", "Z")
    assert envelope["priority"] == 5
    assert envelope["protocolVersion"] == "1.1"


def test_build_populates_content_digest(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
    request_envelope_metadata: Dict[str, Any],
) -> None:
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_payload(_measurement_payload(valid_payload_data))
    builder.set_envelope_metadata(**_request_metadata(request_envelope_metadata))

    message = builder.build()
    json_output = message.model_dump(by_alias=True, mode="json")
    envelope = next(item for item in json_output["@graph"] if item["@id"] == "#envelope")
    content_digest = envelope["contentDigest"]

    assert content_digest["alg"] == "sha256"
    assert re.fullmatch(r"[A-Fa-f0-9]{64}", content_digest["value"]) is not None
    assert isinstance(content_digest["size"], int)
    assert content_digest["size"] > 0


def _build_original_envelope(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
    request_envelope_metadata: Dict[str, Any],
    correlation_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> PCLEnvelope:
    """Builds a request envelope to use as the envelope argument for build_ack/build_nack."""
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_payload(_measurement_payload(valid_payload_data))
    metadata: Dict[str, Any] = _request_metadata(request_envelope_metadata)
    if correlation_id is not None:
        metadata["correlation_id"] = correlation_id
    if idempotency_key is not None:
        metadata["idempotency_key"] = idempotency_key
    builder.set_envelope_metadata(**metadata)
    message = builder.build()
    return next(item for item in message.graph if isinstance(item, PCLEnvelope))


def test_build_ack_swaps_sender_receiver_and_echoes_fields(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
    request_envelope_metadata: Dict[str, Any],
) -> None:
    original = _build_original_envelope(
        builder_defaults,
        valid_payload_data,
        request_envelope_metadata,
        correlation_id="pcl-req-00042",
    )

    ack = build_ack(original)

    assert ack.sender == original.receiver
    assert ack.receiver == original.sender
    assert ack.action == "ack"
    assert ack.schema_ == DEFAULT_SCHEMAS["ack"]
    assert ack.capabilities == original.capabilities
    assert ack.project == original.project
    assert ack.sample == original.sample
    assert ack.correlation_id == "pcl-req-00042"
    assert ack.content_ref == "#none"
    assert ack.authz is None


def test_build_ack_correlation_id_falls_back_to_original_identifier(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
    request_envelope_metadata: Dict[str, Any],
) -> None:
    original = _build_original_envelope(builder_defaults, valid_payload_data, request_envelope_metadata)

    ack = build_ack(original)

    assert ack.correlation_id == original.identifier


def test_build_ack_job_id_sets_identifier(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
    request_envelope_metadata: Dict[str, Any],
) -> None:
    original = _build_original_envelope(builder_defaults, valid_payload_data, request_envelope_metadata)

    ack_with_job_id = build_ack(original, job_id="job-12345678")
    ack_without_job_id = build_ack(original)

    assert ack_with_job_id.identifier == "job-12345678"
    assert ack_without_job_id.identifier.startswith("urn:uuid:")


def test_build_ack_validates_against_envelope_schema(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
    request_envelope_metadata: Dict[str, Any],
    key_pair: Any,
) -> None:
    original = _build_original_envelope(builder_defaults, valid_payload_data, request_envelope_metadata)

    ack = build_ack(original, job_id="job-12345678")
    ack_data = ack.model_dump(mode="json", by_alias=True, exclude_none=True)
    ack_data["authz"] = {"type": "DetachedJWS", "jws": Signer(private_key=key_pair).sign(ack_data)}

    valid, error = validate_structure(ack_data)

    assert valid, error


def test_build_nack_returns_envelope_and_error_linked_by_content_ref(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
    request_envelope_metadata: Dict[str, Any],
) -> None:
    original = _build_original_envelope(
        builder_defaults,
        valid_payload_data,
        request_envelope_metadata,
        correlation_id="pcl-req-00042",
    )

    nack_envelope, error = build_nack(
        original, code=PCLErrorCode.SCHEMA_MISMATCH, reason="Envelope failed schema validation"
    )

    assert nack_envelope.action == "nack"
    assert nack_envelope.schema_ == DEFAULT_SCHEMAS["nack"]
    assert nack_envelope.content_ref == {"@id": "#error"}
    assert error.id == "#error"
    assert error.code == PCLErrorCode.SCHEMA_MISMATCH
    assert error.reason == "Envelope failed schema validation"
    assert error.correlation_id == nack_envelope.correlation_id == "pcl-req-00042"


def test_build_nack_carries_faults(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
    request_envelope_metadata: Dict[str, Any],
) -> None:
    original = _build_original_envelope(builder_defaults, valid_payload_data, request_envelope_metadata)
    faults = [PCLErrorFault(message="Value must match pattern", path="/capabilities/0")]

    _, error = build_nack(original, code=PCLErrorCode.SCHEMA_MISMATCH, reason="bad", faults=faults)

    assert error.faults == faults


def test_build_nack_validates_against_envelope_and_error_schemas(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
    request_envelope_metadata: Dict[str, Any],
    key_pair: Any,
) -> None:
    original = _build_original_envelope(builder_defaults, valid_payload_data, request_envelope_metadata)

    nack_envelope, error = build_nack(original, code=PCLErrorCode.INTERNAL_ERROR, reason="Unexpected failure")

    envelope_data = nack_envelope.model_dump(mode="json", by_alias=True, exclude_none=True)
    envelope_data["authz"] = {"type": "DetachedJWS", "jws": Signer(private_key=key_pair).sign(envelope_data)}
    envelope_valid, envelope_error = validate_structure(envelope_data)
    assert envelope_valid, envelope_error

    error_data = error.model_dump(mode="json", by_alias=True, exclude_none=True)
    error_valid, error_error = validate_structure(error_data, schema_filename="error.json")
    assert error_valid, error_error


def test_pclerror_to_json_round_trip() -> None:
    error = PCLError(code=PCLErrorCode.NOT_FOUND, reason="Sample not found")

    parsed = json.loads(error.to_json())

    assert parsed["@id"] == "#error"
    assert parsed["code"] == "NOT_FOUND"
    assert parsed["reason"] == "Sample not found"
    assert "correlationId" not in parsed


def test_content_digest_is_deterministic_for_fixed_content(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
    request_envelope_metadata: Dict[str, Any],
) -> None:
    first_builder = PCLMessageBuilder(**builder_defaults)
    first_builder.set_payload(_measurement_payload(valid_payload_data))
    first_builder.set_envelope_metadata(**_request_metadata(request_envelope_metadata))

    second_builder = PCLMessageBuilder(**builder_defaults)
    second_builder.set_payload(_measurement_payload(valid_payload_data))
    second_builder.set_envelope_metadata(**_request_metadata(request_envelope_metadata))

    first_message = first_builder.build().model_dump(by_alias=True, mode="json")
    second_message = second_builder.build().model_dump(by_alias=True, mode="json")

    first_envelope = next(item for item in first_message["@graph"] if item["@id"] == "#envelope")
    second_envelope = next(item for item in second_message["@graph"] if item["@id"] == "#envelope")

    assert first_envelope["contentDigest"]["value"] == second_envelope["contentDigest"]["value"]
    assert first_envelope["contentDigest"]["size"] == second_envelope["contentDigest"]["size"]


def test_sign_requires_content(builder_defaults: Dict[str, str], key_pair: Any) -> None:
    builder = PCLMessageBuilder(**builder_defaults)

    with pytest.raises(RuntimeError, match="Message payload has not been set"):
        builder.sign(Signer(private_key=key_pair))


def test_sign_cannot_be_called_twice(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
    request_envelope_metadata: Dict[str, Any],
    key_pair: Any,
) -> None:
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_payload(_measurement_payload(valid_payload_data))
    builder.set_envelope_metadata(**_request_metadata(request_envelope_metadata))
    signer = Signer(private_key=key_pair)

    builder.sign(signer)

    with pytest.raises(RuntimeError, match="Cannot call sign\(\) more than once"):
        builder.sign(signer)


@pytest.mark.parametrize(
    "mutation_call",
    [
        lambda b, p, m: b.set_payload(_measurement_payload(p)),
        lambda b, _, m: b.set_envelope_metadata(correlation_id="pcl-req-00042"),
        lambda b, _, m: b.set_envelope_metadata(**_request_metadata(m, ttl="PT10M")),
    ],
)
def test_mutations_after_sign_are_rejected(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
    request_envelope_metadata: Dict[str, Any],
    key_pair: Any,
    mutation_call: Callable[[PCLMessageBuilder, Dict[str, Any], Dict[str, Any]], Any],
) -> None:
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_payload(_measurement_payload(valid_payload_data))
    builder.set_envelope_metadata(**_request_metadata(request_envelope_metadata))
    builder.sign(Signer(private_key=key_pair))

    with pytest.raises(RuntimeError, match="Cannot modify builder after sign\(\) has been called"):
        mutation_call(builder, valid_payload_data, request_envelope_metadata)
