# PCL Exchange

<a href="https://github.com/htmdec/pcl-exchange" target="_blank" rel="noopener noreferrer">
  <img width="191" height="20" alt="image" src="https://github.com/user-attachments/assets/d7aafa45-ba2c-452a-adef-2132b839d49e" />
</a>

PCL Exchange is a Python library for creating, signing, receiving, and validating machine-actionable messages between Programmable Cloud Laboratories (PCLs). Each message is an RO-Crate JSON-LD document with a signed routing envelope and a typed scientific payload.

The project provides a small interoperability foundation for asynchronous lab-to-lab exchange. It combines Pydantic models, JSON Schema, SHACL, and Ed25519 detached JWS signatures so that a message carries its structure, context, and integrity information with it.

> **Status:** This project is in alpha. It provides exchange-message primitives and validation, not a transport broker, public-key discovery service, or workflow execution engine.

## Contents

- [What it provides](#what-it-provides)
- [How messages work](#how-messages-work)
- [Install](#install)
- [Quick start](#quick-start)
- [Receive and validate](#receive-and-validate)
- [Supported actions](#supported-actions)
- [Responses and callbacks](#responses-and-callbacks)
- [Repository guide](#repository-guide)
- [Development](#development)

## What it provides

- RO-Crate JSON-LD packaging for PCL action messages.
- Typed Pydantic payload models for five laboratory exchange actions.
- Ed25519 detached JWS signing and verification for envelopes.
- JSON Schema validation for envelope structure and SHACL validation for payload semantics.
- Receiver-side parsing that reports actionable validation errors.
- `ack` and `nack` response builders, plus an HTTP callback client with retries for transient failures.

## How messages work

A PCL Exchange message is an RO-Crate with two primary nodes:

1. **Envelope:** identifies the sender and receiver, declares the action and schema, carries routing metadata, links to the content, and contains a detached JWS signature.
2. **Content:** carries the domain-specific request or data description as JSON-LD.

When a receiver calls `parse_and_validate_crate`, the library:

1. Parses the JSON-LD crate and locates the `#envelope` and its referenced content.
2. Validates the envelope against the bundled [JSON Schema](schemas/envelope.json).
3. Resolves the sender's public key through your supplied resolver and verifies the Ed25519 detached JWS.
4. Validates the content against the bundled SHACL shape for the declared action.

The package does not prescribe how peers discover each other, exchange public keys, authorize work, or transport messages. Those concerns belong to the deployment using PCL Exchange.

## Install

PCL Exchange requires Python 3.9 or later. To work from a clone of this repository, install it in editable mode with its development dependencies:

```bash
python -m pip install -e ".[dev]"
```

For library-only dependencies, omit `.[dev]`.

## Quick start

Create a measurement request, add envelope metadata, sign it with an Ed25519 key, and serialize the resulting RO-Crate:

```python
from jwcrypto import jwk

from pcl_exchange.builder import PCLMessageBuilder
from pcl_exchange.crypto import Signer
from pcl_exchange.models import PCLMeasurementRequestContent

private_key = jwk.JWK.generate(kty="OKP", crv="Ed25519")

payload = PCLMeasurementRequestContent.create(
    instrument_ref={"@id": "urn:example:instrument:xrd-01"},
    sample_ref={"@id": "igsn:EXAMPLE0001"},
    method_ref={"@id": "urn:example:method:xrd-powder-v1"},
    params={
        "scan_range": {"val": "10 90", "unit": "deg 2theta"},
        "step": {"val": 0.02, "unit": "deg"},
    },
)

builder = PCLMessageBuilder(
    sender_id="https://ror.org/0sndfake1",
    receiver_id="https://ror.org/0rcvfake1",
    action_type="request_measurement",
)
builder.set_payload(payload)
builder.set_envelope_metadata(
    project="doi:10.5072/example.project",
    sample="igsn:EXAMPLE0001",
    capabilities=["xrd.powder.theta-2theta"],
    respond_to="https://sender.example.org/pcl/callback",
    correlation_id="request-2026-0001",
)
builder.sign(Signer(private_key))

crate = builder.build()
crate_json = crate.to_json()
```

Replace these placeholder identifiers with persistent identifiers and endpoints appropriate to your deployment. The builder includes the RO-Crate context, computes a SHA-256 digest of the content, and seals the builder after signing so signed fields cannot be modified.

## Receive and validate

The receiver is responsible for mapping a sender identifier to a trusted public key. In production, the resolver should return the sender's trusted public key, not the private key used in this demonstration.

```python
from jwcrypto import jwk

from pcl_exchange.receiver import parse_and_validate_crate

def resolve_public_key(sender_id: str) -> jwk.JWK:
    if sender_id != "https://ror.org/0sndfake1":
        raise LookupError(sender_id)
    return private_key

result = parse_and_validate_crate(crate_json, resolve_public_key)

if result.valid:
    envelope = result.envelope
    content = result.content
    print(f"Accepted {envelope['action']} from {envelope['sender']}")
else:
    for error in result.errors:
        print(f"{error.code}: {error.message}")
```

`parse_and_validate_crate` accepts a Python dictionary, a JSON string, or a `pathlib.Path`. A string that names an existing file is read as a path; otherwise it is parsed as JSON text. The returned `CrateParseResult` includes the extracted envelope and content, a validation result, errors, and the SHACL report when semantic validation is run.

## Supported actions

| Envelope action | Content model | Purpose |
| --- | --- | --- |
| `request_measurement` | `PCLMeasurementRequestContent` | Request an instrument measurement for a sample using a declared method and parameters. |
| `register_data` | `PCLRegisterDataContent` | Register a dataset, its project/sample context, provenance, and distribution details. |
| `launch_workflow` | `PCLLaunchWorkflowContent` | Describe a workflow to launch, including language, parameters, and optional repository or container references. |
| `update_metadata` | `PCLUpdateMetadataContent` | Replace supported metadata fields on a target resource. |
| `cancel_job` | `PCLCancelJobContent` | Cancel an originating request by its shared `correlationId`. |

The action-specific SHACL files live in [schemas/shapes](schemas/shapes). In the current profile, `update_metadata` is replace-only and permits `name`, `description`, `license`, and `keywords`; it does not provide merge, deletion, or arbitrary JSON Patch behavior.

## Responses and callbacks

Use `build_ack` to create a minimal acknowledgement envelope or `build_nack` to pair a negative acknowledgement envelope with a structured `PCLError`. Response envelopes reverse the original sender and receiver and preserve relevant correlation and idempotency fields.

`CallbackClient` posts a response crate as `application/ld+json` to a `respondTo` URL. It retries connection/timeout failures and HTTP `429`, `500`, `502`, `503`, and `504` responses. The response helpers create unsigned envelopes; deployments should define and apply their own response-signing policy where required.

```python
from pcl_exchange.builder import build_ack
from pcl_exchange.callback import CallbackClient
from pcl_exchange.models import PCLEnvelope

received_envelope = PCLEnvelope.model_validate(result.envelope)
ack = build_ack(received_envelope, job_id="receiver-job-42")
delivery = CallbackClient().send("https://sender.example.org/pcl/callback", ack)
```

`build_ack` expects a `PCLEnvelope` model. Convert the validated envelope dictionary, as shown above, or use an envelope model maintained by your application.

## Repository guide

| Location | Description |
| --- | --- |
| [src/pcl_exchange/models.py](src/pcl_exchange/models.py) | JSON-LD Pydantic models for envelopes, content, messages, and errors. |
| [src/pcl_exchange/builder.py](src/pcl_exchange/builder.py) | Fluent message builder and response helpers. |
| [src/pcl_exchange/crypto.py](src/pcl_exchange/crypto.py) | Canonicalization, content digests, Ed25519 signing, and verification. |
| [src/pcl_exchange/receiver.py](src/pcl_exchange/receiver.py) | End-to-end crate parsing, signature verification, and validation orchestration. |
| [src/pcl_exchange/validation.py](src/pcl_exchange/validation.py) | JSON Schema and SHACL validation APIs. |
| [schemas](schemas) | Bundled envelope/error schemas and action-specific SHACL shapes. |
| [examples/pcl_action_crate_example.json](examples/pcl_action_crate_example.json) | Signed measurement-request RO-Crate example. |
| [examples/pcl_workflow_crate_example.json](examples/pcl_workflow_crate_example.json) | Workflow-launch RO-Crate example. |
| [examples/workflow_demo.ipynb](examples/workflow_demo.ipynb) | Notebook demonstration of the workflow example. |
| [tests](tests) | Executable examples of building, signing, receiving, validation, and callback behavior. |

## Development

Run the test suite from an activated Python environment:

```bash
python -m pytest
```

On Unix-like systems, the [Makefile](Makefile) also provides these targets:

```bash
make install
make test
make validate
make build
```

`make validate` checks the committed examples against the bundled JSON Schema and SHACL shapes.

## Contributing and license

Please report bugs and interoperability questions through the [issue tracker](https://github.com/htmdec/pcl-exchange/issues). The project is distributed under the [MIT License](LICENSE).
