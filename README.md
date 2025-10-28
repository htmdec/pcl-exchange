# PCL Exchange proposal using RO-Crate Profile, Schemas, and Shapes

This repository captures MADICES week conception for a minimal, interoperable **PCL-to-PCL exchange** pattern. It benefited from conversations with Peter Kraus (TU-Berlin) and Matthew  Evans (Cambridge) and Simon Stier (Fraunh).  It uses:
- **RO-Crate** as the packaging and JSON-LD context carrier
- **JSON Schema** for validating the *envelope* and *error contract*
- **SHACL** shapes for validating content nodes for measurement requests and workflow launches

### What is the minimum viable contract for a receiving PCL? Can the following list be minimized? 


1. Who and where

   * Identifiers for sending PCL (ROR), person (ORCID), and public key reference (DID)
   * Intended receiver identifier (ROR) (maybe? not sure really)
   * Stable message id, creation time, and protocol/profile version (

2. Payload understandability

   * Canonical schema identifier and version for the payload body
   * Encoding and optional compression or encryption info (?)
   * Content checksum for verification check

3. Intent (what to do with the content) 

   * Action verb from a closed vocabulary, for example: `register_data`, `request_measurement`, `launch_workflow`, `update_metadata`, `cancel_job`(can we agree a simple schema or can this be done by context interpretation?)
   * Minimal capability requirement expressed as a feature tag, for example: `capability: xrd/powder/θ–2θ`, `workflow: cwl@v1.2`

4. About which research object

   * Project PID (DataCite DOI or RAiD)
   * Sample PID (IGSN)
   * Optional: workflow, instrument, and facility identifiers.

5. Authorization

   * Token or other credential with scope 
   * Data use constraints? (there will be users who want their data to be private; may need an ontology for the options so a receiver can decide if they can honor the contraints.

6. Routing and responses

   * Acknowledge receipt with a callback channel
   * Schedule constraintes like deadline and priority.

7. Provenance crumbs

   * who constructed the payload 
   * when
   * from which upstream artifacts.



### Others for v.2?

Not necessary but useful?

* Version negotiation workflows
* Replay protection for action requests.
* Validation hooks (JSON Schema or SHACL shape URI)
* Explicit time zone and units
* Error contract
* Data sensitivity tagging

#### Ontology stack

**Do not** invent a new ontology. Compose a small stack and use an RO-Crate profile to bundle it.

* RO-Crate as the container and JSON-LD context carrier, with a profile URI that says “this is a PCL-to-PCL action crate.”
* W3C PROV-O for provenance of the message and any included data or workflow.
* schema.org types for high level objects (Dataset, SoftwareSourceCode, CreativeWork).
* CWL and CWLProv or WfProv/WfDesc for workflows and runs when the intent is to execute.
* PIDs:
  * Project: DOI or RAiD
  * Sample: IGSN.
  * People: ORCID. 
  * Organizations: ROR. 
  * Instruments or facilities: PIDInst (DataCite) and RRID? 
  * Units: QUDT or OM for quantities and units.
  * W3C Verifiable Credentials/Presentations for signed, portable permissions.
  * ODRL for machine readable data use policy terms.
  * Events: map the envelope to CloudEvents fields so you can move it over Kafka, NATS, or HTTP consistently.

## Two layers inside the RO-Crate

1. Envelope entity (machine routing and validation)

* `type`: `PCLActionEnvelope` (a profile class)
* `profile`: URI of the RO-Crate profile
* `id`, `time`, `sender`, `receiver`
* `schema`: URI for the body schema and version
* `hash`, `size`, `encoding`, `encryption`
* `action`: controlled vocab
* `capabilities`: list of required features
* `authz`: JWT in detached JWS form, or a Verifiable Presentation by reference

2. Content entity (domain payload)

* For data: a `Dataset` with distributions, checksums, and PIDs, plus PROV links.
* For workflows: a `SoftwareSourceCode` or `ComputationalWorkflow` with a CWL file, parameters object, and optional tool references.
* For measurement requests: an `Action` with `instrument`, `sample`, `method`, `parameters`, and `acceptanceCriteria` (a workflow basically)

### Minimal JSON-LD sketch inside an RO-Crate

Trying to be compact and start the idea. More or less the same pattern for data registration or workflow launch.


### Recommended “PCL Action Crate” profile

Define one RO-Crate profile URI that nails down:

* The required envelope properties above and an allowed `action` vocabulary.
* Which PIDs you expect for project and sample.
* Which workflow description profiles you accept (CWL, WfProv, etc).
* Which auth artifacts are acceptable (JWT with JWS, Verifiable Presentation).
* A JSON Schema and a SHACL shape for conformance testing.

### Assemble a standard interoperable model from standard pieces:

* RO-Crate for packaging and JSON-LD context.
* PROV-O for provenance.
* CWLProv or WfProv for workflows and runs.
* QUDT or OM for quantities and units.
* ODRL and DUO for data use constraints where needed.
* W3C VCs for portable, signed authorization evidence.
* CloudEvents for event metadata symmetry across transports.

This approach keeps you inside living ecosystems and standards, lets you validate with off-the-shelf tools, and gives you room to evolve by versioning a small RO-Crate profile rather than inventing a new ontology.

###Schema for the PCLActionEnvelope
* JSON Schema (Draft 2020-12) for the PCLActionEnvelope.
* Turtle SHACL shape for a measurement request content entity inside the RO-Crate (the `#content` node)  

### SHACL content entity for measurement requests

Validates `#content` node in the crate graph when the envelope action is `request_measurement`. Ensures a minimal action with an instrument, a sample reference, a method reference, optional acceptance criteria, and parameter entries. It also checks common identifier patterns.

### Notes and next steps

* If you will carry numeric parameters with units, prefer `schema:value` as a number plus `qudt:unit` linking to a QUDT unit IRI. The current shape allows either plain text units or QUDT IRIs so teams can migrate gradually.
* For workflows, create a sibling shape `pcl:WorkflowLaunchShape` that targets `prov:Plan` or `schema:SoftwareSourceCode` with required CWL file presence and parameter object; the pattern is identical to the measurement request.



## Quickstart (local)

```bash
# Optional: create and activate a virtual environment for Python tools (should move this to conda or uv)
python3 -m venv .venv && source .venv/bin/activate

# Install tools and run validations
make install
make validate
```

### Requirements
- Node.js (for ajv-cli) and Python 3.9+ (for pyshacl)
- SSH keys set up for GitHub or HTTPS credentials

## Thinking behind this:
### What is the minimum viable contract for a receiving PCL? Can the following list be minimized? 

1. Who and where

   * Identifiers for sending PCL (ROR), person (ORCID), and public key reference (DID)
   * Intended receiver identifier (ROR) (maybe? not sure really)
   * Stable message id, creation time, and protocol/profile version (

2. Payload understandability

   * Canonical schema identifier and version for the payload body
   * Encoding and optional compression or encryption info (?)
   * Content checksum for verification check

3. Intent (what to do with the content) 

   * Action verb from a closed vocabulary, for example: `register_data`, `request_measurement`, `launch_workflow`, `update_metadata`, `cancel_job`(can we agree a simple schema or can this be done by context interpretation?)
   * Minimal capability requirement expressed as a feature tag, for example: `capability: xrd/powder/θ–2θ`, `workflow: cwl@v1.2`

4. About which research object

   * Project PID (DataCite DOI or RAiD)
   * Sample PID (IGSN)
   * Optional: workflow, instrument, and facility identifiers.

5. Authorization

   * Token or other credential with scope 
   * Data use constraints? (there will be users who want their data to be private; may need an ontology for the options so a receiver can decide if they can honor the contraints.

6. Routing and responses

   * Acknowledge receipt with a callback channel
   * Schedule constraintes like deadline and priority.

7. Provenance crumbs

   * who constructed the payload 
   * when
   * from which upstream artifacts.



### Others for v.2?

Not necessary but useful?

* Version negotiation workflows
* Replay protection for action requests.
* Validation hooks (JSON Schema or SHACL shape URI)
* Explicit time zone and units
* Error contract
* Data sensitivity tagging

#### Ontology stack

**Do not** invent a new ontology. Compose a small stack and use an RO-Crate profile to bundle it.

* RO-Crate as the container and JSON-LD context carrier, with a profile URI that says “this is a PCL-to-PCL action crate.”
* W3C PROV-O for provenance of the message and any included data or workflow.
* schema.org types for high level objects (Dataset, SoftwareSourceCode, CreativeWork).
* CWL and CWLProv or WfProv/WfDesc for workflows and runs when the intent is to execute.
* PIDs:
  * Project: DOI or RAiD
  * Sample: IGSN.
  * People: ORCID. 
  * Organizations: ROR. 
  * Instruments or facilities: PIDInst (DataCite) and RRID? 
  * Units: QUDT or OM for quantities and units.
  * W3C Verifiable Credentials/Presentations for signed, portable permissions.
  * ODRL for machine readable data use policy terms.
  * Events: map the envelope to CloudEvents fields so you can move it over Kafka, NATS, or HTTP consistently.

## Two layers inside the RO-Crate

1. Envelope entity (machine routing and validation)

* `type`: `PCLActionEnvelope` (a profile class)
* `profile`: URI of the RO-Crate profile
* `id`, `time`, `sender`, `receiver`
* `schema`: URI for the body schema and version
* `hash`, `size`, `encoding`, `encryption`
* `action`: controlled vocab
* `capabilities`: list of required features
* `authz`: JWT in detached JWS form, or a Verifiable Presentation by reference

2. Content entity (domain payload)

* For data: a `Dataset` with distributions, checksums, and PIDs, plus PROV links.
* For workflows: a `SoftwareSourceCode` or `ComputationalWorkflow` with a CWL file, parameters object, and optional tool references.
* For measurement requests: an `Action` with `instrument`, `sample`, `method`, `parameters`, and `acceptanceCriteria` (a workflow basically)

# Minimal JSON-LD sketch inside an RO-Crate found in Examples directory

Trying to be compact and start the idea. More or less the same pattern for data registration or workflow launch. 



