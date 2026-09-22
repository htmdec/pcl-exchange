from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from .crypto import compute_content_digest
from .models import (
    DEFAULT_SCHEMAS,
    PCLContentBase,
    PCLMessage,
    PCLEnvelope,
    PCLError,
    PCLErrorCode,
    PCLErrorFault,
    ROCrateMetadata,
    ROCrateRoot,
)


ALLOWED_ACTION_TYPES = tuple(DEFAULT_SCHEMAS.keys())

_RO_CRATE_CONTEXT: List[Any] = [
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
    }
]


class PCLMessageBuilder:
    def __init__(self, sender_id: str, receiver_id: str, action_type: str) -> None:
        if action_type not in ALLOWED_ACTION_TYPES:
            allowed_values = ", ".join(ALLOWED_ACTION_TYPES)
            raise ValueError(
                f"Unsupported action type '{action_type}'. Allowed values: {allowed_values}."
            )
        self.sender: str = sender_id
        self.receiver: str = receiver_id
        self.action_type: str = action_type
        self.schema_uri: str = DEFAULT_SCHEMAS[action_type]
        self.envelope_uuid: str = f"urn:uuid:{uuid.uuid4()}"
        self.creation_timestamp: datetime = datetime.now(timezone.utc)
        self.payload: Optional[PCLContentBase] = None
        self._envelope_metadata: Dict[str, Any] = {}
        self.authz: Optional[Dict[str, str]] = None
        self._sealed: bool = False

    def _check_not_sealed(self) -> None:
        if self._sealed:
            raise RuntimeError("Cannot modify builder after sign() has been called.")
        
    def set_payload(self, payload: PCLContentBase) -> PCLMessageBuilder:
        self._check_not_sealed()
        self.payload = payload
        return self

    def set_envelope_metadata(self, **kwargs: Any) -> PCLMessageBuilder:
        self._check_not_sealed()
        self._envelope_metadata.update(kwargs)
        return self

    def _create_envelope_model(self, authz_data: Optional[Dict[str, str]] = None) -> PCLEnvelope:
        """
        Creates the PCLEnvelope model.
        """
        if self.payload is None:
            raise RuntimeError("Message payload has not been set. Call set_payload() first.")

        content_digest: Optional[Dict[str, Any]] = None
        payload_data = self.payload.model_dump(mode="json", by_alias=True, exclude_none=True)
        content_digest = compute_content_digest(payload_data)

        envelope_data: Dict[str, Any] = {
            "id": "#envelope",
            "sender": self.sender,
            "receiver": self.receiver,
            "schema_": self.schema_uri,
            "action": self.action_type,
            "identifier": self.envelope_uuid,      # overrides default_factory=uuid
            "date_created": self.creation_timestamp, # overrides default_factory=datetime
            "content_ref": {"@id": self.payload.id},
            "content_digest": content_digest,
            "authz": authz_data,
        }
        envelope_data.update(self._envelope_metadata)
        filtered_data = {key: value for key, value in envelope_data.items() if value is not None}

        return PCLEnvelope(**filtered_data)

    def sign(self, signer: Any) -> None:
        if self._sealed:
            raise RuntimeError("Cannot call sign() more than once for the same builder.")
        if self.payload is None:
            raise RuntimeError("Message payload has not been set. Call set_payload() before signing.")

        temp_envelope = self._create_envelope_model(authz_data=None)
        envelope_data = temp_envelope.model_dump(
            mode='json', 
            by_alias=True, 
            exclude_none=True
        )
        
        jws_string = signer.sign(envelope_data)
        
        self.authz = {
            "type": "DetachedJWS",
            "jws": jws_string
        }
        self._sealed = True

    def build(self) -> PCLMessage:
        """Finalizes the message construction and returns a PCLMessage instance."""
        if not self.payload:
            raise ValueError("Message payload has not been set. Call set_payload() before building.")

        envelope = self._create_envelope_model(authz_data=self.authz)
        
        graph_items = [
            ROCrateMetadata(),
            ROCrateRoot(hasPart=[{"@id": "#envelope"}, {"@id": self.payload.id}]),
            envelope,
            self.payload
        ]
        
        return PCLMessage(context=_RO_CRATE_CONTEXT, graph=graph_items)


def _build_response_envelope(
    original: PCLEnvelope,
    action: str,
    content_ref: Union[Dict[str, str], str],
    identifier: Optional[str] = None,
) -> PCLEnvelope:
    """Builds an unsigned response envelope that swaps sender/receiver and echoes routing fields from `original`."""
    envelope_data: Dict[str, Any] = {
        "id": "#envelope",
        "sender": original.receiver,
        "receiver": original.sender,
        "schema_": DEFAULT_SCHEMAS[action],
        "action": action,
        "capabilities": original.capabilities,
        "project": original.project,
        "sample": original.sample,
        "identifier": identifier,
        "content_ref": content_ref,
        "authz": None,
        "correlation_id": original.correlation_id or original.identifier,
        "idempotency_key": original.idempotency_key,
    }
    filtered_data = {key: value for key, value in envelope_data.items() if value is not None}
    return PCLEnvelope(**filtered_data)


def build_ack(envelope: PCLEnvelope, job_id: Optional[str] = None) -> PCLEnvelope:
    """Builds a minimal, unsigned ack PCLEnvelope in response to `envelope`."""
    return _build_response_envelope(envelope, action="ack", content_ref="#none", identifier=job_id)


def build_nack(
    envelope: PCLEnvelope,
    code: PCLErrorCode,
    reason: str,
    faults: Optional[List[PCLErrorFault]] = None,
) -> Tuple[PCLEnvelope, PCLError]:
    """Builds an unsigned nack PCLEnvelope plus its PCLError content, in response to `envelope`."""
    correlation_id = envelope.correlation_id or envelope.identifier
    error = PCLError(
        code=code,
        reason=reason,
        correlation_id=correlation_id,
        idempotency_key=envelope.idempotency_key,
        faults=faults,
    )
    nack_envelope = _build_response_envelope(envelope, action="nack", content_ref={"@id": error.id})
    return nack_envelope, error


def build_response_message(envelope: PCLEnvelope, content: Optional[PCLError] = None) -> PCLMessage:
    """Wraps a response envelope (+ optional PCLError content) into an RO-Crate PCLMessage for transport."""
    has_part: List[Dict[str, str]] = [{"@id": envelope.id}]
    graph_items: List[Any] = [ROCrateMetadata(), ROCrateRoot(hasPart=has_part), envelope]

    if content is not None:
        if content.id is None:
            raise ValueError("content must have an '@id' to be referenced from the RO-Crate root's hasPart list.")
        has_part.append({"@id": content.id})
        graph_items.append(content.model_dump(mode="json", by_alias=True, exclude_none=True))

    return PCLMessage(context=_RO_CRATE_CONTEXT, graph=graph_items)