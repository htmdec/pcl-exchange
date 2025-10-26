# what is the minimum a receiving PCL needs?

Think of this as the “MVP contract” between sender and receiver.

1. **Who and where**

   * Sender identifier and public key reference (organization ROR and/or DID, person ORCID).
   * Intended receiver identifier (maybe? not sure really)
   * Stable message id, creation time, and protocol/profile version.

2. **What the payload is**

   * Canonical **schema identifier** and version for the payload body.
   * Media type, encoding, and optional compression and encryption info.
   * Content checksum and size for integrity checks.

3. **Why and how to act (intent)**

   * Action verb from a closed vocabulary, for example: `register_data`, `request_measurement`, `launch_workflow`, `update_metadata`, `cancel_job`.
   * Minimal capability requirement expressed as a feature tag, for example: `capability: xrd/powder/θ–2θ`, `workflow: cwl@v1.2`.

4. **About which research object**

   * Project PID (for example, DOI, ARK, Handle).
   * Sample PID (for example, IGSN) and optional material system tags.
   * Optional run, workflow, instrument, and facility identifiers.

5. **Authorization to act**

   * A verifiable authorization artifact bound to the sender identity and the specific action, for example a signed token or verifiable credential with scopes tied to the project and sample PIDs and an expiry.
   * Optional data use constraints and consent references.

6. **Routing and responses**

   * Required acknowledgements and the callback or topic for status events.
   * Correlation or idempotency key to make retries safe.
   * Optional deadline and priority.

7. **Provenance crumbs**

   * Minimal PROV trail: who constructed the payload, when, and from which upstream artifacts.

That is the irreducible core for a receiving PCL to accept, understand, verify, and act.

# Useful extras you will likely want

These are not strictly minimal, but they prevent real headaches.

* **Version negotiation**: profile URI and a semantic version to allow evolution.
* **Replay protection**: nonce plus short TTL for action requests.
* **Validation hooks**: a JSON Schema or SHACL shape URI for the declared schema.
* **Time zone and units**: explicit IANA time zone and a units vocabulary for numeric fields.
* **Error contract**: a small, standard error shape with codes and human text.
* **Data sensitivity**: tags like `export_control: EAR99` or references to an institutional policy.
* **Data location**: if transferring by reference, include signed URLs or DRS identifiers.

# A pragmatic ontology stack that already exists

You do not need to invent a new ontology. Compose a small stack and use an RO-Crate profile to bundle it.

* **RO-Crate** as the container and JSON-LD context carrier, with a **profile** URI that says “this is a PCL-to-PCL action crate.”
* **W3C PROV-O** for provenance of the message and any included data or workflow.
* **schema.org** types for high level objects (Dataset, SoftwareSourceCode, CreativeWork).
* **CWL and CWLProv** or **WfProv/WfDesc** for workflows and runs when the intent is to execute.
* **PIDs**:

  * **Project**: DOI or ARK.
  * **Sample**: **IGSN**.
  * **People**: **ORCID**. Organizations: **ROR**. Instruments or facilities: persistent URIs you mint.
* **Units**: **QUDT** or **OM** for quantities and units.
* **Authorization and policy**:

  * **W3C Verifiable Credentials/Presentations** for signed, portable permissions.
  * **ODRL** for machine readable data use policy terms.
  * Optionally **GA4GH DUO** codes when biomedical style data use statements are relevant.
* **Events**: map the envelope to **CloudEvents** fields so you can move over Kafka, NATS, or HTTP consistently.

# Shape it as two layers inside the RO-Crate

1. **Envelope entity** (machine routing and validation)

* `type`: `PCLActionEnvelope` (your profile class)
* `profile`: URI of your RO-Crate profile
* `id`, `time`, `sender`, `receiver`
* `schema`: URI for the body schema and version
* `hash`, `size`, `encoding`, `encryption`
* `action`: controlled vocab
* `capabilities`: list of required features
* `authz`: either a JWT in detached JWS form, or a Verifiable Presentation by reference
* `respondTo`: callback endpoint or topic
* `ttl`, `deadline`, `priority`
* `correlationId`, `idempotencyKey`

2. **Content entity** (domain payload)

* For data: a `Dataset` with distributions, checksums, and PIDs, plus PROV links.
* For workflows: a `SoftwareSourceCode` or `ComputationalWorkflow` with a CWL file, parameters object, and optional tool references.
* For measurement requests: an `Action` with `instrument`, `sample`, `method`, `parameters`, and `acceptanceCriteria`.

# Minimal JSON-LD sketch inside an RO-Crate

This is compact and captures the spirit. The same pattern works for data registration or workflow launch.

```json
{
  "@context": [
    "https://w3id.org/ro/crate/1.1/context",
    {"prov": "http://www.w3.org/ns/prov#", "odrl": "http://www.w3.org/ns/odrl/2/", "qudt": "http://qudt.org/schema/qudt/", "duo": "http://purl.obolibrary.org/obo/duo#"}
  ],
  "@graph": [
    {
      "@id": "ro-crate-metadata.json",
      "@type": "CreativeWork",
      "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
      "about": {"@id": "./"}
    },
    {
      "@id": "./",
      "@type": "Dataset",
      "name": "PCL Action Crate",
      "hasPart": [{"@id": "#envelope"}, {"@id": "#content"}],
      "identifier": "urn:uuid:1c6b3e2f-..."
    },
    {
      "@id": "#envelope",
      "@type": "PCLActionEnvelope",
      "profile": "https://w3id.org/pcl-profile/action/v1",
      "identifier": "urn:uuid:1c6b3e2f-...",
      "dateCreated": "2025-10-25T08:15:30Z",
      "sender": {"@id": "https://ror.org/03yrm5c26"},
      "receiver": {"@id": "https://ror.org/01bj3aw27"},
      "schema": "https://w3id.org/pcl-schema/measure-request/v1.0",
      "contentRef": {"@id": "#content"},
      "action": "request_measurement",
      "capabilities": ["xrd.powder.theta-2theta"],
      "project": "doi:10.1234/project.5678",
      "sample": "igsn:XYZ12345",
      "authz": {"@id": "#vp"},
      "respondTo": "https://aimd-l.example.org/hooks/status",
      "ttl": "PT10M",
      "correlationId": "pcl-req-00042",
      "idempotencyKey": "pcl-req-00042-v1"
    },
    {
      "@id": "#content",
      "@type": "Action",
      "instrument": {"@id": "urn:aimd:instrument:proto-xrd-01"},
      "object": {"@id": "igsn:XYZ12345"},
      "prov:wasAttributedTo": {"@id": "https://orcid.org/0000-0002-..."},
      "prov:used": {"@id": "#method"},
      "expectsAcceptanceCriteria": {"@id": "#criteria"},
      "parameter": [
        {"@type": "PropertyValue", "name": "scan_range", "value": "10 90", "unitText": "deg 2θ"},
        {"@type": "PropertyValue", "name": "step", "value": 0.02, "unitText": "deg"}
      ]
    },
    {
      "@id": "#method",
      "@type": "CreativeWork",
      "name": "Powder XRD theta–2theta",
      "identifier": "urn:aimd:method:xrd:powder:theta-2theta:v1"
    },
    {
      "@id": "#criteria",
      "@type": "CreativeWork",
      "text": "SNR ≥ 20 at peak near 2θ=28 deg; max dose 1 mC."
    },
    {
      "@id": "#vp",
      "@type": "VerifiablePresentation",
      "odrl:hasPolicy": [{"@id": "#policy"}],
      "duo:hasDataUsePermission": [{"@id": "duo:0000006"}]
    },
    {
      "@id": "#policy",
      "@type": "odrl:Policy",
      "odrl:permission": [{"odrl:action": "use"}],
      "odrl:constraint": [{"odrl:leftOperand": "purpose", "odrl:operator": "eq", "odrl:rightOperand": "materials-research"}]
    }
  ]
}
```

# How this maps to transport

* Over Kafka or NATS, publish the **envelope** as a CloudEvents compatible record with `dataref` pointing to the RO-Crate object store location, or include the crate inline if small.
* Over HTTP, the envelope fields become headers and the RO-Crate JSON-LD is the body.
* The receiver validates: signature, audience, expiry, schema, project and sample authorization, then checks capability match before acting.

# Recommended “PCL Action Crate” profile

Define one RO-Crate **profile** URI that nails down:

* The required envelope properties above and an allowed `action` vocabulary.
* Which PIDs you expect for project and sample.
* Which workflow description profiles you accept (CWL, WfProv, etc).
* Which auth artifacts are acceptable (JWT with JWS, Verifiable Presentation).
* A JSON Schema and a SHACL shape for conformance testing.

# Is there an existing single data model that does all of this?

Not as a single monolith, but you can assemble a standard, interoperable model from well adopted pieces:

* RO-Crate for packaging and JSON-LD context.
* PROV-O for provenance.
* CWLProv or WfProv for workflows and runs.
* QUDT or OM for quantities and units.
* ODRL and DUO for data use constraints where needed.
* W3C VCs for portable, signed authorization evidence.
* CloudEvents for event metadata symmetry across transports.

This approach keeps you inside living ecosystems and standards, lets you validate with off-the-shelf tools, and gives you room to evolve by versioning a small RO-Crate profile rather than inventing a new ontology.

If you want, I can draft a first pass of the JSON Schema for the `PCLActionEnvelope` and a SHACL shape for the content section that you can drop into a schema registry and start testing against real messages.

--
2.
Here is a clean first pass you can drop into a registry and start validating against. It includes:

* A JSON Schema (Draft 2020-12) for the **PCLActionEnvelope**.
* A SHACL shape (Turtle) for a **measurement request content** entity inside your RO-Crate (the `#content` node), aligned with the example we discussed.

# JSON Schema — PCLActionEnvelope (Draft 2020-12)

```json
{
  "$id": "https://w3id.org/pcl-profile/action/v1/schema/envelope.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "PCLActionEnvelope",
  "type": "object",
  "required": [
    "profile",
    "identifier",
    "dateCreated",
    "sender",
    "receiver",
    "schema",
    "action",
    "contentRef",
    "project",
    "sample",
    "capabilities",
    "authz"
  ],
  "properties": {
    "profile": {
      "type": "string",
      "format": "uri",
      "const": "https://w3id.org/pcl-profile/action/v1"
    },
    "identifier": {
      "type": "string",
      "pattern": "^(urn:uuid:[0-9a-fA-F-]{36}|[A-Za-z0-9._~:-]{8,})$"
    },
    "dateCreated": { "type": "string", "format": "date-time" },
    "sender": {
      "type": "string",
      "oneOf": [
        { "pattern": "^https://ror\\.org/[0-9a-hjkmnp-z]{9}$" },
        { "pattern": "^https://orcid\\.org/\\d{4}-\\d{4}-\\d{4}-\\d{3}[\\dX]$" },
        { "format": "uri" }
      ],
      "description": "ROR preferred for organizations, ORCID for people"
    },
    "receiver": {
      "type": "string",
      "oneOf": [
        { "pattern": "^https://ror\\.org/[0-9a-hjkmnp-z]{9}$" },
        { "format": "uri" }
      ]
    },
    "schema": {
      "type": "string",
      "format": "uri",
      "description": "URI of the body schema and version (for example https://w3id.org/pcl-schema/measure-request/v1.0)"
    },
    "schemaHash": {
      "type": "object",
      "required": ["alg", "value"],
      "properties": {
        "alg": { "type": "string", "enum": ["sha256", "sha384", "sha512"] },
        "value": { "type": "string", "pattern": "^[A-Fa-f0-9]{64,128}$" }
      },
      "additionalProperties": false
    },
    "contentRef": {
      "description": "Link to the content entity inside the RO-Crate graph or an external URI",
      "oneOf": [
        { "type": "string", "pattern": "^#.+$" },
        { "type": "string", "format": "uri" }
      ]
    },
    "contentDigest": {
      "type": "object",
      "required": ["alg", "value"],
      "properties": {
        "alg": { "type": "string", "enum": ["sha256", "sha384", "sha512"] },
        "value": { "type": "string", "pattern": "^[A-Fa-f0-9]{64,128}$" },
        "size": { "type": "integer", "minimum": 0 }
      },
      "additionalProperties": false
    },
    "encoding": {
      "type": "string",
      "enum": ["identity", "gzip", "zstd"]
    },
    "encryption": {
      "type": "object",
      "required": ["alg"],
      "properties": {
        "alg": { "type": "string" },
        "kid": { "type": "string" }
      },
      "additionalProperties": false
    },
    "action": {
      "type": "string",
      "enum": [
        "register_data",
        "request_measurement",
        "launch_workflow",
        "update_metadata",
        "cancel_job",
        "ack",
        "nack"
      ]
    },
    "capabilities": {
      "type": "array",
      "minItems": 1,
      "items": { "type": "string", "pattern": "^[a-z0-9][a-z0-9./_-]{2,}$" },
      "description": "Required features, for example xrd.powder.theta-2theta"
    },
    "project": {
      "type": "string",
      "oneOf": [
        { "pattern": "^doi:10\\.[0-9]{4,9}/\\S+$" },
        { "pattern": "^ark:/.+$" },
        { "format": "uri" }
      ]
    },
    "sample": {
      "type": "string",
      "oneOf": [
        { "pattern": "^igsn:[A-Za-z0-9./:-]{5,}$" },
        { "format": "uri" }
      ]
    },
    "authz": {
      "description": "Authorization artifact",
      "oneOf": [
        {
          "type": "object",
          "required": ["type", "jws"],
          "properties": {
            "type": { "const": "DetachedJWS" },
            "jws": { "type": "string" }
          },
          "additionalProperties": false
        },
        {
          "type": "object",
          "required": ["type", "vpRef"],
          "properties": {
            "type": { "const": "VerifiablePresentationRef" },
            "vpRef": { "type": "string", "format": "uri" }
          },
          "additionalProperties": false
        }
      ]
    },
    "respondTo": { "type": "string", "format": "uri" },
    "ttl": {
      "type": "string",
      "pattern": "^P(?!$)(\\d+Y)?(\\d+M)?(\\d+D)?(T(\\d+H)?(\\d+M)?(\\d+S)?)?$",
      "description": "ISO 8601 duration"
    },
    "deadline": { "type": "string", "format": "date-time" },
    "priority": { "type": "integer", "minimum": 0, "maximum": 9 },
    "correlationId": {
      "type": "string",
      "pattern": "^[A-Za-z0-9_.:-]{6,128}$"
    },
    "idempotencyKey": {
      "type": "string",
      "pattern": "^[A-Za-z0-9_.:-]{6,128}$"
    },
    "protocolVersion": {
      "type": "string",
      "pattern": "^v?\\d+\\.\\d+(\\.\\d+)?$",
      "default": "1.0"
    },
    "location": {
      "type": "object",
      "properties": {
        "transport": { "type": "string", "enum": ["http", "kafka", "nats", "s3", "drs"] },
        "topicOrPath": { "type": "string" }
      },
      "additionalProperties": false
    },
    "sensitivity": {
      "type": "string",
      "enum": ["public", "internal", "restricted", "export_control"]
    },
    "policyRefs": {
      "type": "array",
      "items": { "type": "string", "format": "uri" }
    },
    "prov": {
      "type": "object",
      "properties": {
        "wasAttributedTo": { "type": "string", "format": "uri" },
        "generatedAtTime": { "type": "string", "format": "date-time" }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false,
  "examples": [
    {
      "profile": "https://w3id.org/pcl-profile/action/v1",
      "identifier": "urn:uuid:1c6b3e2f-7b1a-4c2e-9f3a-1a2b3c4d5e6f",
      "dateCreated": "2025-10-25T08:15:30Z",
      "sender": "https://ror.org/03yrm5c26",
      "receiver": "https://ror.org/01bj3aw27",
      "schema": "https://w3id.org/pcl-schema/measure-request/v1.0",
      "action": "request_measurement",
      "capabilities": ["xrd.powder.theta-2theta"],
      "project": "doi:10.1234/project.5678",
      "sample": "igsn:XYZ12345",
      "contentRef": "#content",
      "authz": { "type": "DetachedJWS", "jws": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..." },
      "respondTo": "https://aimd-l.example.org/hooks/status",
      "ttl": "PT10M",
      "correlationId": "pcl-req-00042",
      "idempotencyKey": "pcl-req-00042-v1"
    }
  ]
}
```

# SHACL — Content entity for a measurement request

This validates the `#content` node in your RO-Crate graph when the envelope action is `request_measurement`. It ensures a minimal Action with an instrument, a sample reference, a method reference, optional acceptance criteria, and parameter entries. It also checks common identifier patterns.

```turtle
@prefix sh:    <http://www.w3.org/ns/shacl#> .
@prefix xsd:   <http://www.w3.org/2001/XMLSchema#> .
@prefix prov:  <http://www.w3.org/ns/prov#> .
@prefix schema: <http://schema.org/> .
@prefix qudt:  <http://qudt.org/schema/qudt/> .
@prefix pcl:   <https://w3id.org/pcl-profile/action/v1/terms#> .

###############################################################################
# Root shape for a PCL measurement request content entity
###############################################################################

pcl:MeasurementRequestShape
    a sh:NodeShape ;
    sh:targetClass schema:Action ;
    sh:property [
        sh:path schema:instrument ;
        sh:minCount 1 ;
        sh:nodeKind sh:IRI ;
        sh:message "schema:instrument must be an IRI identifying the instrument" ;
    ] ;
    sh:property [
        sh:path schema:object ;
        sh:minCount 1 ;
        sh:nodeKind sh:IRI ;
        sh:pattern "^igsn:|^https?://" ;
        sh:message "schema:object must reference the sample, preferably an IGSN" ;
    ] ;
    sh:property [
        sh:path prov:wasAttributedTo ;
        sh:maxCount 1 ;
        sh:nodeKind sh:IRI ;
    ] ;
    sh:property [
        sh:path prov:used ;
        sh:minCount 1 ;
        sh:nodeKind sh:IRI ;
        sh:message "prov:used must reference a method definition IRI" ;
    ] ;
    sh:property [
        sh:path schema:expectsAcceptanceCriteria ;
        sh:maxCount 1 ;
        sh:node pcl:AcceptanceCriteriaShape ;
    ] ;
    sh:property [
        sh:path schema:parameter ;
        sh:minCount 1 ;
        sh:node pcl:ParameterShape ;
    ] .

###############################################################################
# Parameter shape (schema:PropertyValue with name and value, optional unit)
###############################################################################

pcl:ParameterShape
    a sh:NodeShape ;
    sh:targetClass schema:PropertyValue ;
    sh:property [
        sh:path schema:name ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
    ] ;
    sh:property [
        sh:path schema:value ;
        sh:minCount 1 ;
    ] ;
    sh:property [
        sh:path schema:unitText ;
        sh:maxCount 1 ;
        sh:datatype xsd:string ;
    ] ;
    sh:property [
        sh:path qudt:unit ;
        sh:maxCount 1 ;
        sh:nodeKind sh:IRI ;
    ] .

###############################################################################
# Acceptance criteria (simple CreativeWork with free text or structured refs)
###############################################################################

pcl:AcceptanceCriteriaShape
    a sh:NodeShape ;
    sh:targetClass schema:CreativeWork ;
    sh:property [
        sh:path schema:text ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
    ] .

###############################################################################
# Optional method definition shape (if dereferenced for validation)
###############################################################################

pcl:MethodShape
    a sh:NodeShape ;
    sh:targetClass schema:CreativeWork ;
    sh:property [
        sh:path schema:identifier ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
    ] ;
    sh:property [
        sh:path schema:name ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
    ] .

###############################################################################
# Identifier helper shapes (can be used with sh:node on specific paths)
###############################################################################

pcl:IGSNIdentifierShape
    a sh:NodeShape ;
    sh:property [
        sh:path [ sh:alternativePath ( schema:identifier schema:sameAs ) ] ;
        sh:minCount 1 ;
        sh:pattern "^igsn:[A-Za-z0-9./:-]{5,}$" ;
    ] .

pcl:DOIIdentifierShape
    a sh:NodeShape ;
    sh:property [
        sh:path [ sh:alternativePath ( schema:identifier schema:sameAs ) ] ;
        sh:minCount 1 ;
        sh:pattern "^doi:10\\.[0-9]{4,9}/\\S+$" ;
    ] .
```

# Notes and next steps

* If you want the SHACL to enforce that the `schema:object` is the same IGSN as the envelope `sample`, pass the envelope value into the data graph and add `sh:equals` between those two nodes or use SHACL-SPARQL with a parameter.
* If you will carry numeric parameters with units, prefer `schema:value` as a number plus `qudt:unit` linking to a QUDT unit IRI. The current shape allows either plain text units or QUDT IRIs so teams can migrate gradually.
* For workflows, create a sibling shape `pcl:WorkflowLaunchShape` that targets `prov:Plan` or `schema:SoftwareSourceCode` with required CWL file presence and parameter object; the pattern is identical to the measurement request.
* In the JSON Schema, if you decide to transport only RO-Crate by reference, make `contentRef` `format: uri` only and mark `#content` use as a profile-level rule rather than a schema rule.

If you want, I can also draft `pcl:WorkflowLaunchShape` plus a JSON Schema for a tiny “error contract” so PCLs can return machine-readable nacks.


--

## Now making minimalistic with Pull-Push Distinction (maybe this becomes push in *my* PCL and pull for *navigating* between PCLs?

--
## Here is the updated codes:
Here you go: a compact SHACL shape for launching a workflow and a tiny JSON Schema error contract for machine-readable nacks. Both align with the envelope and content patterns we already set.

# SHACL — `pcl:WorkflowLaunchShape` (Turtle)

```turtle
@prefix sh:     <http://www.w3.org/ns/shacl#> .
@prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .
@prefix schema: <http://schema.org/> .
@prefix prov:   <http://www.w3.org/ns/prov#> .
@prefix qudt:   <http://qudt.org/schema/qudt/> .
@prefix pcl:    <https://w3id.org/pcl-profile/action/v1/terms#> .

###############################################################################
# Root shape for a workflow launch content entity
# Targets a CWL or similar descriptor carried as SoftwareSourceCode
###############################################################################

pcl:WorkflowLaunchShape
    a sh:NodeShape ;
    sh:targetClass schema:SoftwareSourceCode ;
    sh:property [
        sh:path schema:name ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
    ] ;
    sh:property [
        sh:path schema:programmingLanguage ;
        sh:minCount 1 ;
        sh:message "Declare the workflow language. Example: CWL v1.2" ;
    ] ;
    # One of: inline descriptor file in the crate OR remote descriptor URI
    sh:or (
        [ sh:property [
              sh:path schema:hasPart ;
              sh:minCount 1 ;
              sh:node pcl:WorkflowDescriptorFileShape ;
          ] ]
        [ sh:property [
              sh:path schema:codeRepository ;
              sh:minCount 1 ;
              sh:nodeKind sh:IRI ;
              sh:message "Repository or descriptor URI required when no file is embedded" ;
          ] ]
    ) ;
    # Optional container images to ensure supply chain integrity
    sh:property [
        sh:path pcl:usesContainer ;
        sh:node pcl:ContainerImageShape ;
        sh:minCount 0 ;
        sh:maxCount 50 ;
    ] ;
    # Parameter set to pass to the workflow at launch
    sh:property [
        sh:path schema:parameter ;
        sh:minCount 1 ;
        sh:node pcl:ParameterShape ;
    ] ;
    # Optional sample and project binding if not only in the envelope
    sh:property [
        sh:path schema:object ;
        sh:maxCount 1 ;
        sh:nodeKind sh:IRI ;
        sh:message "Reference the primary research object (for example the IGSN sample)" ;
    ] ;
    sh:property [
        sh:path schema:isPartOf ;
        sh:maxCount 1 ;
        sh:nodeKind sh:IRI ;
        sh:message "Reference the project PID (for example a DOI or ARK)" ;
    ] ;
    # Optional expected outputs description
    sh:property [
        sh:path schema:result ;
        sh:maxCount 1 ;
        sh:node pcl:ExpectedResultShape ;
    ] .

###############################################################################
# Descriptor file embedded in the RO-Crate (for example a CWL file)
###############################################################################

pcl:WorkflowDescriptorFileShape
    a sh:NodeShape ;
    sh:targetClass schema:CreativeWork ;
    sh:property [
        sh:path schema:encodingFormat ;
        sh:minCount 1 ;
        sh:in ( "application/cwl" "text/x-yaml" "application/json" ) ;
        sh:message "Descriptor must declare an encoding format. Use application/cwl for CWL." ;
    ] ;
    sh:property [
        sh:path schema:contentUrl ;
        sh:minCount 1 ;
        sh:nodeKind sh:IRI ;
        sh:message "Point to the embedded file path or external URL" ;
    ] ;
    sh:property [
        sh:path schema:sha256 ;
        sh:maxCount 1 ;
        sh:datatype xsd:string ;
    ] .

###############################################################################
# Container image shape (OCI style; digest is strongly recommended)
###############################################################################

pcl:ContainerImageShape
    a sh:NodeShape ;
    sh:property [
        sh:path schema:identifier ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
        sh:message "Use a canonical image reference. Example: ghcr.io/org/tool:1.4.3" ;
    ] ;
    sh:property [
        sh:path pcl:digest ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
        sh:pattern "^sha256:[A-Fa-f0-9]{64}$" ;
        sh:message "Include OCI digest to pin the image" ;
    ] ;
    sh:property [
        sh:path schema:contentUrl ;
        sh:maxCount 1 ;
        sh:nodeKind sh:IRI ;
        sh:message "Optional SBOM or signature URL" ;
    ] .

###############################################################################
# Parameter shape (same as in measurement requests)
###############################################################################

pcl:ParameterShape
    a sh:NodeShape ;
    sh:targetClass schema:PropertyValue ;
    sh:property [
        sh:path schema:name ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
    ] ;
    sh:property [
        sh:path schema:value ;
        sh:minCount 1 ;
    ] ;
    sh:property [
        sh:path qudt:unit ;
        sh:maxCount 1 ;
        sh:nodeKind sh:IRI ;
    ] ;
    sh:property [
        sh:path schema:unitText ;
        sh:maxCount 1 ;
        sh:datatype xsd:string ;
    ] .

###############################################################################
# Expected results (optional)
###############################################################################

pcl:ExpectedResultShape
    a sh:NodeShape ;
    sh:targetClass schema:CreativeWork ;
    sh:property [
        sh:path schema:about ;
        sh:minCount 1 ;
    ] ;
    sh:property [
        sh:path schema:distribution ;
        sh:maxCount 10 ;
    ] .
```

Notes

* Use `pcl:usesContainer` as a predicate in your context that points from the workflow content node to one or more container descriptors.
* Accept either an embedded descriptor file in the crate (`schema:hasPart`) or a repository or descriptor URL (`schema:codeRepository`).
* If you want to strictly require CWL, change `sh:in` for `schema:encodingFormat` to only `application/cwl`.

---

# JSON Schema — tiny error contract for nacks (Draft 2020-12)

This is intentionally small and transport agnostic. It supports correlation, retry guidance, and a short fault list that can point to fields by JSON Pointer or JSONPath.

```json
{
  "$id": "https://w3id.org/pcl-profile/action/v1/schema/error.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "PCLError",
  "type": "object",
  "required": ["type", "timestamp", "code", "reason"],
  "additionalProperties": false,
  "properties": {
    "type": {
      "type": "string",
      "const": "https://w3id.org/pcl-profile/action/v1#Error"
    },
    "timestamp": { "type": "string", "format": "date-time" },
    "code": {
      "type": "string",
      "enum": [
        "INVALID_ENVELOPE",
        "UNAUTHORIZED",
        "FORBIDDEN",
        "SCHEMA_MISMATCH",
        "UNSUPPORTED_ACTION",
        "CAPABILITY_MISMATCH",
        "NOT_FOUND",
        "CONFLICT",
        "RATE_LIMITED",
        "TEMPORARY_FAILURE",
        "INTERNAL_ERROR"
      ]
    },
    "reason": { "type": "string", "minLength": 1, "maxLength": 2048 },
    "correlationId": {
      "type": "string",
      "pattern": "^[A-Za-z0-9_.:-]{6,128}$"
    },
    "idempotencyKey": {
      "type": "string",
      "pattern": "^[A-Za-z0-9_.:-]{6,128}$"
    },
    "httpStatus": { "type": "integer", "minimum": 100, "maximum": 599 },
    "retriable": { "type": "boolean", "default": false },
    "retryAfter": {
      "description": "Either an RFC 7231 HTTP-date or a delta-seconds value",
      "oneOf": [
        { "type": "integer", "minimum": 1 },
        { "type": "string", "format": "date-time" }
      ]
    },
    "faults": {
      "description": "Fine grained validation faults",
      "type": "array",
      "minItems": 0,
      "maxItems": 50,
      "items": {
        "type": "object",
        "required": ["message"],
        "additionalProperties": false,
        "properties": {
          "path": {
            "description": "JSON Pointer or JSONPath to the offending field",
            "type": "string"
          },
          "schema": {
            "description": "URI of the violated schema or shape",
            "type": "string",
            "format": "uri"
          },
          "message": { "type": "string", "minLength": 1, "maxLength": 512 }
        }
      }
    },
    "details": {
      "description": "Machine readable extra data for debugging or recovery",
      "type": "object",
      "additionalProperties": true
    }
  },
  "examples": [
    {
      "type": "https://w3id.org/pcl-profile/action/v1#Error",
      "timestamp": "2025-10-25T08:41:12Z",
      "code": "SCHEMA_MISMATCH",
      "reason": "Envelope failed JSON Schema validation",
      "httpStatus": 422,
      "retriable": false,
      "correlationId": "pcl-req-00042",
      "idempotencyKey": "pcl-req-00042-v1",
      "faults": [
        {
          "path": "/capabilities/0",
          "schema": "https://w3id.org/pcl-profile/action/v1/schema/envelope.json",
          "message": "Value must match ^[a-z0-9][a-z0-9./_-]{2,}$"
        }
      ],
      "details": {
        "profile": "https://w3id.org/pcl-profile/action/v1",
        "schemaVersion": "1.0"
      }
    }
  ]
}
```

Implementation tips

* Return this error body with HTTP 4xx or 5xx when using HTTP. If you are on a message bus, publish it on the response topic with the same `correlationId`.
* Set `retriable` and optionally `retryAfter` when the failure is transient. For example, service maintenance or temporary capacity issues.
* Use the same `correlationId` and `idempotencyKey` from the request envelope so the sender can reconcile retries and nacks.

If you want, I can also add a SHACL rule that ties `schema:programmingLanguage` to a controlled vocabulary and asserts `CWL v1.2` when your envelope action is `launch_workflow`.
