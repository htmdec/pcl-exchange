import copy
import json
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List

from jwcrypto import jwk

from conftest import MOCK_DATASET_DOI, MOCK_PROJECT_DOI, MOCK_RECEIVER_ROR, MOCK_SAMPLE_IGSN, MOCK_SENDER_ROR
from pcl_exchange.builder import PCLMessageBuilder
from pcl_exchange.crypto import Signer
from pcl_exchange.models import PCLMeasurementRequestContent
from pcl_exchange.receiver import parse_and_validate_crate


def _never_called(sender_id: str) -> jwk.JWK:
    raise AssertionError(f"resolver should not have been called for '{sender_id}'")


def _example_resolver(example_sender_public_key: jwk.JWK) -> Callable[[str], jwk.JWK]:
    # NOTE: this ROR is baked into the pre-signed examples/pcl_action_crate_example.json
    # bytes; it can't be swapped for a mock constant without invalidating that signature.
    def _resolve(sender_id: str) -> jwk.JWK:
        if sender_id != "https://ror.org/03yrm5c26":
            raise LookupError(sender_id)
        return example_sender_public_key

    return _resolve


def test_valid_crate_from_path(example_sender_public_key: jwk.JWK) -> None:
    result = parse_and_validate_crate(
        Path("examples") / "pcl_action_crate_example.json", _example_resolver(example_sender_public_key)
    )

    assert result.valid is True
    assert result.errors == []
    assert result.envelope is not None and result.envelope["@id"] == "#envelope"
    assert result.content is not None and result.content["@id"] == "#content"


def test_valid_crate_from_dict(example_action_crate: Dict[str, Any], example_sender_public_key: jwk.JWK) -> None:
    result = parse_and_validate_crate(
        copy.deepcopy(example_action_crate), _example_resolver(example_sender_public_key)
    )

    assert result.valid is True
    assert result.errors == []
    assert result.envelope is not None and result.envelope["@id"] == "#envelope"
    assert result.content is not None and result.content["@id"] == "#content"


def test_valid_crate_from_json_string(
    example_action_crate: Dict[str, Any], example_sender_public_key: jwk.JWK
) -> None:
    result = parse_and_validate_crate(json.dumps(example_action_crate), _example_resolver(example_sender_public_key))

    assert result.valid is True
    assert result.errors == []
    assert result.envelope is not None and result.envelope["@id"] == "#envelope"


def test_missing_envelope_node(example_action_crate: Dict[str, Any]) -> None:
    data = copy.deepcopy(example_action_crate)
    data["@graph"] = [node for node in data["@graph"] if node.get("@id") != "#envelope"]

    result = parse_and_validate_crate(data, _never_called)

    assert result.valid is False
    assert result.envelope is None
    assert result.content is None
    assert [e.code for e in result.errors] == ["MISSING_ENVELOPE"]


def test_content_ref_target_missing(example_action_crate: Dict[str, Any], example_sender_public_key: jwk.JWK) -> None:
    data = copy.deepcopy(example_action_crate)
    for node in data["@graph"]:
        if node.get("@id") == "#envelope":
            node["contentRef"] = {"@id": "#does-not-exist"}

    result = parse_and_validate_crate(data, _example_resolver(example_sender_public_key))

    assert result.valid is False
    assert result.envelope is not None
    assert result.content is None
    # tampering contentRef also invalidates the signature, since it covers the whole envelope
    assert [e.code for e in result.errors] == ["CONTENT_NOT_FOUND", "INVALID_SIGNATURE"]


def test_envelope_schema_violation(example_action_crate: Dict[str, Any], example_sender_public_key: jwk.JWK) -> None:
    data = copy.deepcopy(example_action_crate)
    for node in data["@graph"]:
        if node.get("@id") == "#envelope":
            del node["sender"]

    result = parse_and_validate_crate(data, _example_resolver(example_sender_public_key))

    assert result.valid is False
    assert result.envelope is not None
    assert "sender" not in result.envelope
    # sender is gone, so the signature step can't resolve a sender id either
    assert [e.code for e in result.errors] == ["SCHEMA_VALIDATION_ERROR", "MISSING_SENDER"]


def test_invalid_json_string() -> None:
    result = parse_and_validate_crate("{not valid json", _never_called)

    assert result.valid is False
    assert result.envelope is None
    assert [e.code for e in result.errors] == ["INVALID_JSON"]


def test_missing_path_raises_invalid_json() -> None:
    result = parse_and_validate_crate(Path("does-not-exist.json"), _never_called)

    assert result.valid is False
    assert result.envelope is None
    assert [e.code for e in result.errors] == ["INVALID_JSON"]


def test_generic_sender_resolution_error_is_reported() -> None:
    def _resolver(sender_id: str) -> jwk.JWK:
        raise KeyError(sender_id)

    result = parse_and_validate_crate(
        {
            "@context": ["https://w3id.org/ro/crate/1.1/context"],
            "@graph": [
                {
                    "@id": "#envelope",
                    "@type": "PCLActionEnvelope",
                    "profile": "https://w3id.org/pcl-profile/action/v1",
                    "identifier": "urn:uuid:123",
                    "dateCreated": "2026-01-01T00:00:00Z",
                    "sender": {"@id": "https://example.org/sender"},
                    "receiver": {"@id": "https://example.org/receiver"},
                    "schema": "https://w3id.org/pcl-schema/request-measurement/v1.0",
                    "action": "request_measurement",
                    "contentRef": {"@id": "#content"},
                    "project": MOCK_PROJECT_DOI,
                    "sample": MOCK_SAMPLE_IGSN,
                    "capabilities": ["xrd.powder.theta-2theta"],
                    "authz": {"type": "DetachedJWS", "jws": "abc"},
                },
                {"@id": "#content", "@type": "Dataset", "name": "Example"},
            ],
        },
        _resolver,
    )

    assert result.valid is False
    assert [e.code for e in result.errors] == ["UNKNOWN_SENDER_KEY"]


def test_missing_graph_key() -> None:
    result = parse_and_validate_crate({"@context": "https://w3id.org/ro/crate/1.1/context"}, _never_called)

    assert result.valid is False
    assert result.envelope is None
    assert [e.code for e in result.errors] == ["MISSING_GRAPH"]


def _build_signed_crate(
    key_pair: jwk.JWK, builder_defaults: Dict[str, str], valid_payload_data: Dict[str, Any]
) -> Dict[str, Any]:
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_payload(
        PCLMeasurementRequestContent.create(
            instrument_ref={"@id": valid_payload_data["instrument"]},
            sample_ref={"@id": valid_payload_data["sample"]},
            method_ref={"@id": valid_payload_data["method"]},
            params=valid_payload_data["params"],
        )
    )
    builder.set_envelope_metadata(
        project=MOCK_PROJECT_DOI,
        sample=MOCK_SAMPLE_IGSN,
        capabilities=["xrd.powder.theta-2theta"],
    )
    builder.sign(Signer(private_key=key_pair))
    return json.loads(builder.build().to_json())


def test_signed_crate_verifies(
    key_pair: jwk.JWK, builder_defaults: Dict[str, str], valid_payload_data: Dict[str, Any]
) -> None:
    data = _build_signed_crate(key_pair, builder_defaults, valid_payload_data)

    result = parse_and_validate_crate(data, lambda sender_id: key_pair)

    assert result.valid is True
    assert result.errors == []


def test_tampered_field_invalidates_signature(
    key_pair: jwk.JWK, builder_defaults: Dict[str, str], valid_payload_data: Dict[str, Any]
) -> None:
    data = _build_signed_crate(key_pair, builder_defaults, valid_payload_data)
    for node in data["@graph"]:
        if node.get("@id") == "#envelope":
            node["capabilities"] = ["tampered.capability"]

    result = parse_and_validate_crate(data, lambda sender_id: key_pair)

    assert result.valid is False
    assert [e.code for e in result.errors] == ["INVALID_SIGNATURE"]


def test_tampered_jws_invalidates_signature(
    key_pair: jwk.JWK, builder_defaults: Dict[str, str], valid_payload_data: Dict[str, Any]
) -> None:
    data = _build_signed_crate(key_pair, builder_defaults, valid_payload_data)
    for node in data["@graph"]:
        if node.get("@id") == "#envelope":
            node["authz"]["jws"] = node["authz"]["jws"][:-4] + "abcd"

    result = parse_and_validate_crate(data, lambda sender_id: key_pair)

    assert result.valid is False
    assert [e.code for e in result.errors] == ["INVALID_SIGNATURE"]


def test_unknown_sender_key(
    key_pair: jwk.JWK, builder_defaults: Dict[str, str], valid_payload_data: Dict[str, Any]
) -> None:
    data = _build_signed_crate(key_pair, builder_defaults, valid_payload_data)

    def _resolver(sender_id: str) -> jwk.JWK:
        raise LookupError(sender_id)

    result = parse_and_validate_crate(data, _resolver)

    assert result.valid is False
    assert [e.code for e in result.errors] == ["UNKNOWN_SENDER_KEY"]


def test_missing_signature(
    key_pair: jwk.JWK, builder_defaults: Dict[str, str], valid_payload_data: Dict[str, Any]
) -> None:
    data = _build_signed_crate(key_pair, builder_defaults, valid_payload_data)
    for node in data["@graph"]:
        if node.get("@id") == "#envelope":
            del node["authz"]

    result = parse_and_validate_crate(data, lambda sender_id: key_pair)

    assert result.valid is False
    assert [e.code for e in result.errors] == ["SCHEMA_VALIDATION_ERROR", "MISSING_SIGNATURE"]


def test_unsupported_authz_type(
    key_pair: jwk.JWK, builder_defaults: Dict[str, str], valid_payload_data: Dict[str, Any]
) -> None:
    data = _build_signed_crate(key_pair, builder_defaults, valid_payload_data)
    for node in data["@graph"]:
        if node.get("@id") == "#envelope":
            node["authz"] = {"@id": "#vp"}

    result = parse_and_validate_crate(data, lambda sender_id: key_pair)

    assert result.valid is False
    assert [e.code for e in result.errors] == ["UNSUPPORTED_AUTHZ_TYPE"]


def test_signed_crate_passes_shacl(
    key_pair: jwk.JWK, builder_defaults: Dict[str, str], valid_payload_data: Dict[str, Any]
) -> None:
    data = _build_signed_crate(key_pair, builder_defaults, valid_payload_data)

    result = parse_and_validate_crate(data, lambda sender_id: key_pair)

    assert result.valid is True
    assert result.errors == []
    assert result.shacl_report is not None


def test_shacl_violation_reported(
    key_pair: jwk.JWK, builder_defaults: Dict[str, str], valid_payload_data: Dict[str, Any]
) -> None:
    data = _build_signed_crate(key_pair, builder_defaults, valid_payload_data)
    for node in data["@graph"]:
        if node.get("@id") == "#content":
            del node["object"]

    result = parse_and_validate_crate(data, lambda sender_id: key_pair)

    assert result.valid is False
    assert [e.code for e in result.errors] == ["SHACL_VALIDATION_ERROR"]
    assert result.shacl_report is not None and "object" in result.shacl_report


def test_shacl_skipped_when_schema_invalid(
    key_pair: jwk.JWK, builder_defaults: Dict[str, str], valid_payload_data: Dict[str, Any]
) -> None:
    data = _build_signed_crate(key_pair, builder_defaults, valid_payload_data)
    for node in data["@graph"]:
        if node.get("@id") == "#envelope":
            del node["sender"]

    result = parse_and_validate_crate(data, lambda sender_id: key_pair)

    assert result.valid is False
    assert result.shacl_report is None
    assert not any(e.code == "SHACL_VALIDATION_ERROR" for e in result.errors)


def test_shacl_skipped_when_signature_invalid(
    key_pair: jwk.JWK, builder_defaults: Dict[str, str], valid_payload_data: Dict[str, Any]
) -> None:
    data = _build_signed_crate(key_pair, builder_defaults, valid_payload_data)
    for node in data["@graph"]:
        if node.get("@id") == "#envelope":
            node["capabilities"] = ["tampered.capability"]

    result = parse_and_validate_crate(data, lambda sender_id: key_pair)

    assert result.valid is False
    assert result.shacl_report is None
    assert not any(e.code == "SHACL_VALIDATION_ERROR" for e in result.errors)


def test_no_shape_for_unmapped_action(
    key_pair: jwk.JWK,
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
    monkeypatch: Any,
) -> None:
    """All five v1 actions now have shapes; force the defensive branch via a mocked resolver."""
    monkeypatch.setattr("pcl_exchange.receiver.get_shape_for_action", lambda action: None)

    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_payload(
        PCLMeasurementRequestContent.create(
            instrument_ref={"@id": valid_payload_data["instrument"]},
            sample_ref={"@id": valid_payload_data["sample"]},
            method_ref={"@id": valid_payload_data["method"]},
            params=valid_payload_data["params"],
        )
    )
    builder.set_envelope_metadata(
        project=MOCK_PROJECT_DOI,
        sample=MOCK_SAMPLE_IGSN,
        capabilities=["xrd.powder.theta-2theta"],
    )
    builder.sign(Signer(private_key=key_pair))
    data = json.loads(builder.build().to_json())

    result = parse_and_validate_crate(data, lambda sender_id: key_pair)

    assert result.valid is False
    assert [e.code for e in result.errors] == ["NO_SHAPE_FOR_ACTION"]
    assert result.shacl_report is None


def _build_signed_workflow_crate(key_pair: jwk.JWK) -> Dict[str, Any]:
    """Hand-builds a launch_workflow envelope + SoftwareSourceCode content; PCLMessageBuilder only supports Action content."""
    content: Dict[str, Any] = {
        "@id": "#content",
        "@type": "SoftwareSourceCode",
        "name": "Test Workflow",
        "programmingLanguage": "CWL v1.2",
        "codeRepository": {"@id": "https://example.org/workflows/main"},
        "parameter": [{"@type": "PropertyValue", "name": "scan_range", "value": "10 90"}],
    }
    envelope: Dict[str, Any] = {
        "@id": "#envelope",
        "@type": "PCLActionEnvelope",
        "profile": "https://w3id.org/pcl-profile/action/v1",
        "identifier": f"urn:uuid:{uuid.uuid4()}",
        "dateCreated": "2026-01-01T00:00:00Z",
        "sender": {"@id": MOCK_SENDER_ROR},
        "receiver": {"@id": MOCK_RECEIVER_ROR},
        "schema": "https://w3id.org/pcl-schema/launch-workflow/v1.0",
        "action": "launch_workflow",
        "contentRef": {"@id": "#content"},
        "project": MOCK_PROJECT_DOI,
        "sample": MOCK_SAMPLE_IGSN,
        "capabilities": ["workflow.cwl.launch"],
    }

    jws_string = Signer(key_pair).sign(envelope)
    envelope["authz"] = {"type": "DetachedJWS", "jws": jws_string}

    context = [
        "https://w3id.org/ro/crate/1.1/context",
        {
            "prov": "http://www.w3.org/ns/prov#",
            "qudt": "http://qudt.org/schema/qudt/",
            "parameter": "http://schema.org/parameter",
            "unitText": "http://schema.org/unitText",
        },
    ]
    return {"@context": context, "@graph": [envelope, content]}


def test_workflow_launch_action_dispatches_workflow_shape(key_pair: jwk.JWK) -> None:
    data = _build_signed_workflow_crate(key_pair)

    result = parse_and_validate_crate(data, lambda sender_id: key_pair)

    assert result.valid is True
    assert result.errors == []
    assert result.shacl_report is not None


def _build_signed_action_crate(
    key_pair: jwk.JWK,
    action: str,
    schema_uri: str,
    content: Dict[str, Any],
    capabilities: List[str],
) -> Dict[str, Any]:
    """Hand-builds a signed envelope for the given action; PCLMessageBuilder only supports request_measurement content."""
    envelope: Dict[str, Any] = {
        "@id": "#envelope",
        "@type": "PCLActionEnvelope",
        "profile": "https://w3id.org/pcl-profile/action/v1",
        "identifier": f"urn:uuid:{uuid.uuid4()}",
        "dateCreated": "2026-01-01T00:00:00Z",
        "sender": {"@id": MOCK_SENDER_ROR},
        "receiver": {"@id": MOCK_RECEIVER_ROR},
        "schema": schema_uri,
        "action": action,
        "contentRef": {"@id": "#content"},
        "project": MOCK_PROJECT_DOI,
        "sample": MOCK_SAMPLE_IGSN,
        "capabilities": capabilities,
    }

    jws_string = Signer(key_pair).sign(envelope)
    envelope["authz"] = {"type": "DetachedJWS", "jws": jws_string}

    context = [
        "https://w3id.org/ro/crate/1.1/context",
        {
            "prov": "http://www.w3.org/ns/prov#",
            "qudt": "http://qudt.org/schema/qudt/",
            "parameter": "http://schema.org/parameter",
            "unitText": "http://schema.org/unitText",
            "sha256": "http://schema.org/sha256",
            "generatedAtTime": {
                "@id": "http://www.w3.org/ns/prov#generatedAtTime",
                "@type": "http://www.w3.org/2001/XMLSchema#dateTime",
            },
        },
    ]
    return {"@context": context, "@graph": [envelope, content]}


def test_register_data_action_dispatches_register_data_shape(key_pair: jwk.JWK) -> None:
    """distribution is nested inline, since the receiver only forwards the content node itself to SHACL."""
    content: Dict[str, Any] = {
        "@id": "#content",
        "@type": "Dataset",
        "name": "XRD Run 42 Results",
        "identifier": MOCK_DATASET_DOI,
        "isPartOf": {"identifier": MOCK_PROJECT_DOI},
        "about": {"identifier": MOCK_SAMPLE_IGSN},
        "prov:wasAttributedTo": {"@id": MOCK_SENDER_ROR},
        "generatedAtTime": "2026-01-01T00:00:00Z",
        "distribution": {
            "@type": "DataDownload",
            "contentUrl": {"@id": "https://example.org/data/run-42.zip"},
            "encodingFormat": "application/zip",
            "sha256": "a" * 64,
        },
    }
    data = _build_signed_action_crate(
        key_pair, "register_data", "https://w3id.org/pcl-schema/register-data/v1.0", content, ["data.register"]
    )

    result = parse_and_validate_crate(data, lambda sender_id: key_pair)

    assert result.valid is True
    assert result.errors == []
    assert result.shacl_report is not None


def test_update_metadata_action_dispatches_update_metadata_shape(key_pair: jwk.JWK) -> None:
    content: Dict[str, Any] = {
        "@id": "#content",
        "@type": "UpdateAction",
        "object": {"@id": "https://example.org/datasets/42"},
        "prov:wasAttributedTo": {"@id": MOCK_SENDER_ROR},
        "parameter": [{"@type": "PropertyValue", "name": "description", "value": "Updated description text"}],
    }
    data = _build_signed_action_crate(
        key_pair, "update_metadata", "https://w3id.org/pcl-schema/update-metadata/v1.0", content, ["data.update"]
    )

    result = parse_and_validate_crate(data, lambda sender_id: key_pair)

    assert result.valid is True
    assert result.errors == []
    assert result.shacl_report is not None


def test_cancel_job_action_dispatches_cancel_job_shape(key_pair: jwk.JWK) -> None:
    content: Dict[str, Any] = {
        "@id": "#content",
        "@type": "Action",
        "object": {
            "@id": "#cancel-target",
            "@type": "PropertyValue",
            "name": "correlationId",
            "value": "pcl-req-00042",
        },
        "prov:wasAttributedTo": {"@id": MOCK_SENDER_ROR},
    }
    data = _build_signed_action_crate(
        key_pair, "cancel_job", "https://w3id.org/pcl-schema/cancel-job/v1.0", content, ["job.cancel"]
    )

    result = parse_and_validate_crate(data, lambda sender_id: key_pair)

    assert result.valid is True
    assert result.errors == []
    assert result.shacl_report is not None