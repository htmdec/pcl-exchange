import copy
from typing import Any, Dict, List

import pcl_exchange.validation as validation
from conftest import MOCK_DATASET_DOI, MOCK_PROJECT_DOI, MOCK_SAMPLE_IGSN, MOCK_SENDER_ROR
from pcl_exchange.validation import get_shape_for_action, validate_semantics, validate_structure

# Shared JSON-LD context for standalone content-node SHACL fixtures below.
# sha256 is explicitly mapped because the RO-Crate context does not define it.
_CONTENT_CONTEXT: List[Any] = [
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


def test_get_shape_for_action_known_actions() -> None:
    assert get_shape_for_action("register_data") == "shapes/register_data.ttl"
    assert get_shape_for_action("request_measurement") == "shapes/request_measurement.ttl"
    assert get_shape_for_action("launch_workflow") == "shapes/launch_workflow.ttl"
    assert get_shape_for_action("update_metadata") == "shapes/update_metadata.ttl"
    assert get_shape_for_action("cancel_job") == "shapes/cancel_job.ttl"


def test_get_shape_for_action_unmapped_action() -> None:
    assert get_shape_for_action("unknown_action") is None


def test_get_shape_for_action_does_not_read_shape_content(monkeypatch: Any) -> None:
    def fail_if_read(filename: str) -> str:
        raise AssertionError(f"Unexpected schema read: {filename}")

    monkeypatch.setattr(validation, "get_schema_text", fail_if_read)

    assert get_shape_for_action("request_measurement") == "shapes/request_measurement.ttl"

def test_example_compliance(example_action_crate: Dict[str, Any]) -> None:
    data = copy.deepcopy(example_action_crate)

    graph = data.get("@graph", [])
    envelope = next((item for item in graph if item.get("@id") == "#envelope"), None)
    assert envelope is not None, "Example crate missing #envelope node"

    valid, err = validate_structure(envelope)
    assert valid, f"JSON Schema failed: {err}"

    conforms, report = validate_semantics(data, "shapes/request_measurement.ttl")
    assert conforms, f"SHACL failed: {report}"

def test_envelope_with_routing_fields_validates(example_action_crate: Dict[str, Any]) -> None:
    data = copy.deepcopy(example_action_crate)

    graph = data.get("@graph", [])
    envelope = next((item for item in graph if item.get("@id") == "#envelope"), None)
    assert envelope is not None, "Example crate missing #envelope node"

    envelope["respondTo"] = "https://example.org/hooks/status"
    envelope["correlationId"] = "pcl-req-00042"
    envelope["idempotencyKey"] = "pcl-req-00042-v1"
    envelope["ttl"] = "PT10M"
    envelope["deadline"] = "2030-01-01T00:00:00Z"
    envelope["priority"] = 5
    envelope["protocolVersion"] = "1.1"
    envelope["schemaHash"] = {"alg": "sha256", "value": "a" * 64}

    valid, err = validate_structure(envelope)
    assert valid, f"JSON Schema failed: {err}"


def test_register_data_shape_accepts_valid_dataset() -> None:
    data = {
        "@context": _CONTENT_CONTEXT,
        "@graph": [
            {
                "@id": "#content",
                "@type": "Dataset",
                "name": "XRD Run 42 Results",
                "identifier": MOCK_DATASET_DOI,
                "isPartOf": {"identifier": MOCK_PROJECT_DOI},
                "about": {"identifier": MOCK_SAMPLE_IGSN},
                "prov:wasAttributedTo": {"@id": MOCK_SENDER_ROR},
                "generatedAtTime": "2026-01-01T00:00:00Z",
                "distribution": {"@id": "#dist-1"},
            },
            {
                "@id": "#dist-1",
                "@type": "DataDownload",
                "contentUrl": {"@id": "https://example.org/data/run-42.zip"},
                "encodingFormat": "application/zip",
                "sha256": "a" * 64,
            },
        ],
    }

    conforms, report = validate_semantics(data, "shapes/register_data.ttl")
    assert conforms, f"SHACL failed: {report}"


def test_register_data_shape_rejects_dataset_without_distribution() -> None:
    data = {
        "@context": _CONTENT_CONTEXT,
        "@graph": [
            {
                "@id": "#content",
                "@type": "Dataset",
                "name": "XRD Run 42 Results",
                "identifier": MOCK_DATASET_DOI,
                "isPartOf": {"identifier": MOCK_PROJECT_DOI},
                "about": {"identifier": MOCK_SAMPLE_IGSN},
                "prov:wasAttributedTo": {"@id": MOCK_SENDER_ROR},
                "generatedAtTime": "2026-01-01T00:00:00Z",
            }
        ],
    }

    conforms, report = validate_semantics(data, "shapes/register_data.ttl")
    assert not conforms
    assert "distribution" in report


def test_update_metadata_shape_accepts_valid_replacement() -> None:
    data = {
        "@context": _CONTENT_CONTEXT,
        "@graph": [
            {
                "@id": "#content",
                "@type": "UpdateAction",
                "object": {"@id": "https://example.org/datasets/42"},
                "prov:wasAttributedTo": {"@id": MOCK_SENDER_ROR},
                "parameter": [
                    {"@type": "PropertyValue", "name": "description", "value": "Updated description text"}
                ],
            }
        ],
    }

    conforms, report = validate_semantics(data, "shapes/update_metadata.ttl")
    assert conforms, f"SHACL failed: {report}"


def test_update_metadata_shape_rejects_disallowed_field_name() -> None:
    data = {
        "@context": _CONTENT_CONTEXT,
        "@graph": [
            {
                "@id": "#content",
                "@type": "UpdateAction",
                "object": {"@id": "https://example.org/datasets/42"},
                "prov:wasAttributedTo": {"@id": MOCK_SENDER_ROR},
                "parameter": [{"@type": "PropertyValue", "name": "owner", "value": "someone else"}],
            }
        ],
    }

    conforms, report = validate_semantics(data, "shapes/update_metadata.ttl")
    assert not conforms


def test_cancel_job_shape_accepts_valid_correlation_id() -> None:
    data = {
        "@context": _CONTENT_CONTEXT,
        "@graph": [
            {
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
        ],
    }

    conforms, report = validate_semantics(data, "shapes/cancel_job.ttl")
    assert conforms, f"SHACL failed: {report}"


def test_cancel_job_shape_rejects_invalid_correlation_id() -> None:
    data = {
        "@context": _CONTENT_CONTEXT,
        "@graph": [
            {
                "@id": "#content",
                "@type": "Action",
                "object": {
                    "@id": "#cancel-target",
                    "@type": "PropertyValue",
                    "name": "correlationId",
                    "value": "abc",
                },
                "prov:wasAttributedTo": {"@id": MOCK_SENDER_ROR},
            }
        ],
    }

    conforms, report = validate_semantics(data, "shapes/cancel_job.ttl")
    assert not conforms