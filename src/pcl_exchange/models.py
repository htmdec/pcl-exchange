from __future__ import annotations
from typing import List, Optional, Union, Literal, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, SerializeAsAny
from datetime import datetime, timezone
import uuid

ROR_PATTERN = r"^https://ror\.org/[0-9a-hjkmnp-z]{9}$"
ORCID_PATTERN = r"^https://orcid\.org/\d{4}-\d{4}-\d{4}-\d{3}[\dX]$"
IGSN_PATTERN = r"^igsn:[A-Za-z0-9./:-]{5,}$"
PROTOCOL_VERSION_DEFAULT = "0.1.1"
DEFAULT_SCHEMAS: Dict[str, str] = {
    "register_data": "https://w3id.org/pcl-schema/register-data/v1.0",
    "request_measurement": "https://w3id.org/pcl-schema/measure-request/v1.0",
    "launch_workflow": "https://w3id.org/pcl-schema/launch-workflow/v1.0",
    "update_metadata": "https://w3id.org/pcl-schema/update-metadata/v1.0",
    "cancel_job": "https://w3id.org/pcl-schema/cancel-job/v1.0",
    "ack": "https://w3id.org/pcl-schema/ack/v1.0",
    "nack": "https://w3id.org/pcl-schema/nack/v1.0",
}


class PCLContentBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    id: str = Field(alias="@id")
    type: str = Field(alias="@type")

class PropertyValue(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    type: Literal["PropertyValue"] = Field("PropertyValue", alias="@type")
    name: str
    value: Union[str, float, int, bool, Dict[str, str]]
    unit_text: Optional[str] = Field(None, alias="unitText")
    unit_ref: Optional[Dict[str, str]] = Field(None, alias="qudt:unit")
    
class PCLMeasurementRequestContent(PCLContentBase):
    """Structural payload model for request_measurement content."""
    model_config = ConfigDict(populate_by_name=True)
    type: Literal["Action"] = Field("Action", alias="@type")
    instrument: Dict[str, str] = Field(..., description="Pointer to Instrument IRI")
    object: Dict[str, str] = Field(..., description="Pointer to Sample (IGSN)")
    used: Dict[str, str] = Field(..., alias="prov:used", description="Pointer to Method")
    parameters: List[PropertyValue] = Field(..., alias="parameter")
    was_attributed_to: Optional[Dict[str, str]] = Field(None, alias="prov:wasAttributedTo")
    expects_acceptance_criteria: Optional[Dict[str, Any]] = Field(None, alias="schema:expectsAcceptanceCriteria")
    
    @classmethod
    def create(
        cls,
        instrument_ref: Dict[str, str],
        sample_ref: Dict[str, str],
        method_ref: Dict[str, str],
        params: Dict[str, Dict[str, Any]],
        was_attributed_to_ref: Optional[Dict[str, str]] = None,
        expects_acceptance_criteria: Optional[Dict[str, Any]] = None,
    ) -> PCLMeasurementRequestContent:
        p_list = [
            PropertyValue(
                name=k,
                value=v["val"],
                unit_text=v.get("unit"),
                unit_ref=v.get("unit_ref"),
            )
            for k, v in params.items()
        ]
        return cls(
            id="#content",
            instrument=instrument_ref,
            object=sample_ref,
            used=method_ref,
            parameter=p_list,
            was_attributed_to=was_attributed_to_ref,
            expects_acceptance_criteria=expects_acceptance_criteria,
        )


class PCLRegisterDataContent(PCLContentBase):
    """Structural payload model for register_data content."""
    model_config = ConfigDict(populate_by_name=True)
    type: Literal["Dataset"] = Field("Dataset", alias="@type")
    name: str
    identifier: str
    is_part_of: Dict[str, Any] = Field(..., alias="isPartOf")
    about: Dict[str, Any]
    was_attributed_to: Dict[str, str] = Field(..., alias="prov:wasAttributedTo")
    generated_at_time: Optional[str] = Field(None, alias="generatedAtTime")
    policy: Optional[Dict[str, str]] = Field(None, alias="odrl:hasPolicy")
    distribution: Union[Dict[str, Any], List[Dict[str, Any]]]

    @classmethod
    def create(
        cls,
        name: str,
        identifier: str,
        project_ref: Dict[str, Any],
        sample_ref: Dict[str, Any],
        attributed_to_ref: Dict[str, str],
        distribution: Union[Dict[str, Any], List[Dict[str, Any]]],
        generated_at_time: Optional[str] = None,
        policy_ref: Optional[Dict[str, str]] = None,
    ) -> PCLRegisterDataContent:
        return cls(
            id="#content",
            name=name,
            identifier=identifier,
            isPartOf=project_ref,
            about=sample_ref,
            **{"prov:wasAttributedTo": attributed_to_ref},
            generatedAtTime=generated_at_time,
            **{"odrl:hasPolicy": policy_ref},
            distribution=distribution,
        )


class PCLLaunchWorkflowContent(PCLContentBase):
    """Structural payload model for launch_workflow content."""
    model_config = ConfigDict(populate_by_name=True)
    type: Literal["SoftwareSourceCode"] = Field("SoftwareSourceCode", alias="@type")
    name: str
    programming_language: str = Field(..., alias="programmingLanguage")
    parameters: List[PropertyValue] = Field(..., alias="parameter")
    has_part: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = Field(None, alias="hasPart")
    code_repository: Optional[Dict[str, str]] = Field(None, alias="codeRepository")
    uses_container: Optional[List[Dict[str, Any]]] = Field(None, alias="pcl:usesContainer")
    object: Optional[Dict[str, str]] = None
    is_part_of: Optional[Dict[str, str]] = Field(None, alias="isPartOf")
    result: Optional[Dict[str, Any]] = None

    @classmethod
    def create(
        cls,
        name: str,
        programming_language: str,
        params: Dict[str, Dict[str, Any]],
        has_part: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
        code_repository_ref: Optional[Dict[str, str]] = None,
        uses_container: Optional[List[Dict[str, Any]]] = None,
        object_ref: Optional[Dict[str, str]] = None,
        project_ref: Optional[Dict[str, str]] = None,
        result_ref: Optional[Dict[str, Any]] = None,
    ) -> PCLLaunchWorkflowContent:
        p_list = [
            PropertyValue(
                name=k,
                value=v["val"],
                unit_text=v.get("unit"),
                unit_ref=v.get("unit_ref"),
            )
            for k, v in params.items()
        ]
        return cls(
            id="#content",
            name=name,
            programmingLanguage=programming_language,
            parameter=p_list,
            hasPart=has_part,
            codeRepository=code_repository_ref,
            **{"pcl:usesContainer": uses_container},
            object=object_ref,
            isPartOf=project_ref,
            result=result_ref,
        )


class PCLUpdateMetadataContent(PCLContentBase):
    """Structural payload model for update_metadata content."""
    model_config = ConfigDict(populate_by_name=True)
    type: Literal["UpdateAction"] = Field("UpdateAction", alias="@type")
    object: Dict[str, str]
    was_attributed_to: Dict[str, str] = Field(..., alias="prov:wasAttributedTo")
    parameters: List[PropertyValue] = Field(..., alias="parameter")

    @classmethod
    def create(
        cls,
        object_ref: Dict[str, str],
        attributed_to_ref: Dict[str, str],
        updates: Dict[str, Any],
    ) -> PCLUpdateMetadataContent:
        p_list = [PropertyValue(name=k, value=v) for k, v in updates.items()]
        return cls(
            id="#content",
            object=object_ref,
            **{"prov:wasAttributedTo": attributed_to_ref},
            parameter=p_list,
        )


class PCLCancelJobContent(PCLContentBase):
    """Structural payload model for cancel_job content."""
    model_config = ConfigDict(populate_by_name=True)
    type: Literal["Action"] = Field("Action", alias="@type")
    object: Dict[str, Any]
    was_attributed_to: Dict[str, str] = Field(..., alias="prov:wasAttributedTo")
    description: Optional[str] = None

    @classmethod
    def create(
        cls,
        correlation_id: str,
        attributed_to_ref: Dict[str, str],
        description: Optional[str] = None,
    ) -> PCLCancelJobContent:
        cancel_target = {
            "@type": "PropertyValue",
            "name": "correlationId",
            "value": correlation_id,
        }
        return cls(
            id="#content",
            object=cancel_target,
            **{"prov:wasAttributedTo": attributed_to_ref},
            description=description,
        )

class AuthZ(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    type: Literal["DetachedJWS"] = "DetachedJWS"
    jws: str

class PCLEnvelope(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    id: str = Field(alias="@id")
    type: Literal["PCLActionEnvelope"] = Field("PCLActionEnvelope", alias="@type")
    profile: str = "https://w3id.org/pcl-profile/action/v1"

    schema_: str = Field(
        DEFAULT_SCHEMAS["request_measurement"],
        alias="schema"
    )

    identifier: str = Field(default_factory=lambda: f"urn:uuid:{uuid.uuid4()}")
    date_created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="dateCreated")
    
    sender: str = Field(..., pattern=f"{ROR_PATTERN}|{ORCID_PATTERN}")
    receiver: str
    action: Literal[
        "register_data",
        "request_measurement",
        "launch_workflow",
        "update_metadata",
        "cancel_job",
        "ack",
        "nack"
    ]
    
    capabilities: List[str]
    project: str
    sample: str
    
    content_ref: Union[Dict[str, str], str] = Field(..., alias="contentRef")
    content_digest: Optional[Dict[str, Any]] = Field(None, alias="contentDigest")
    authz: AuthZ = None

    respond_to: Optional[str] = Field(None, alias="respondTo")
    ttl: Optional[str] = None
    deadline: Optional[datetime] = None
    priority: Optional[int] = None
    correlation_id: Optional[str] = Field(None, alias="correlationId")
    idempotency_key: Optional[str] = Field(None, alias="idempotencyKey")
    protocol_version: Optional[str] = Field(PROTOCOL_VERSION_DEFAULT, alias="protocolVersion")
    schema_hash: Optional[Dict[str, str]] = Field(None, alias="schemaHash")

class PCLErrorCode(str, Enum):
    INVALID_ENVELOPE = "INVALID_ENVELOPE"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    UNSUPPORTED_ACTION = "UNSUPPORTED_ACTION"
    CAPABILITY_MISMATCH = "CAPABILITY_MISMATCH"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    TEMPORARY_FAILURE = "TEMPORARY_FAILURE"
    INTERNAL_ERROR = "INTERNAL_ERROR"

class PCLErrorFault(BaseModel):
    """Describes a single validation or processing fault."""
    model_config = ConfigDict(populate_by_name=True)
    path: Optional[str] = None
    schema: Optional[str] = None
    message: str

class PCLError(PCLContentBase):
    """Structured error response for PCL action processing."""
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field("#error", alias="@id")
    type: Literal["https://w3id.org/pcl-profile/action/v1#Error"] = Field(
        "https://w3id.org/pcl-profile/action/v1#Error", alias="@type"
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    code: PCLErrorCode
    reason: str
    correlation_id: Optional[str] = Field(None, alias="correlationId")
    idempotency_key: Optional[str] = Field(None, alias="idempotencyKey")
    http_status: Optional[int] = Field(None, alias="httpStatus")
    retriable: Optional[bool] = False
    retry_after: Optional[Union[int, datetime]] = Field(None, alias="retryAfter")
    faults: Optional[List[PCLErrorFault]] = None
    details: Optional[Dict[str, Any]] = None

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True, indent=2, exclude_none=True)

class ROCrateMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field("ro-crate-metadata.json", alias="@id")
    type: Literal["CreativeWork"] = Field("CreativeWork", alias="@type")
    about: Dict[str, str] = Field({"@id": "./"}, alias="about")
    conformsTo: Dict[str, str] = Field({"@id": "https://w3id.org/ro/crate/1.1"}, alias="conformsTo")

    identifier: str = "ro-crate-metadata.json"
    name: str = "RO-Crate Metadata"
    text: str = Field("Metadata descriptor for PCL Exchange", alias="text")

class ROCrateRoot(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field("./", alias="@id")
    type: Literal["Dataset"] = Field("Dataset", alias="@type")
    hasPart: List[Dict[str, str]] = [{"@id": "#envelope"}, {"@id": "#content"}]

class PCLMessage(BaseModel):
    """The full JSON-LD document"""
    model_config = ConfigDict(populate_by_name=True)
    context: List[Any] = Field(..., alias="@context")
    graph: List[Union[ROCrateMetadata, ROCrateRoot, PCLEnvelope, SerializeAsAny[PCLContentBase], Dict[str, Any]]] = Field(..., alias="@graph")

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True, indent=2, exclude_none=True)