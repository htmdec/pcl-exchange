# PCL Exchange proposal using RO-Crate Profile, Schemas, and Shapes

This repository captures MADICES week conception for a minimal, interoperable **PCL-to-PCL exchange** pattern with inspiration from Peter Kraus and Matthew  Evans and Abigail Miller and the Jackson Laboratory data model and the JSON-LD from Simon Stier.  It uses:
- **RO-Crate** as the packaging and JSON-LD context carrier
- **JSON Schema** for validating the *envelope* and *error contract*
- **SHACL** shapes for validating content nodes for measurement requests and workflow launches

## Layout

```
.
├── README.md
├── schemas/
│   ├── envelope.json          # JSON Schema PCLActionEnvelope
│   └── error.json             # JSON Schema PCLError 
├── shapes/
│   ├── measurement_request.ttl  # SHACL — pcl:MeasurementRequestShape
│   └── workflow_launch.ttl      # SHACL — pcl:WorkflowLaunchShape
├── examples/
    └── pcl_action_crate_example.json  # Example RO-Crate JSON-LD graph

```

## An Attempt at Validation

- **Envelope**:
  - Validate with JSON Schema: `schemas/envelope.json`
- **Error (nack) contract**:
  - Validate with JSON Schema: `schemas/error.json`
- **Content**:
  - Validate measurement requests against `shapes/measurement_request.ttl`
  - Validate workflow launches against `shapes/workflow_launch.ttl`

## Assumptions
- The RO-Crate profile identifier is assumed to be `https://w3id.org/pcl-profile/action/v1`
- Units may be expressed via `schema:unitText` (free text) or `qudt:unit` (preferred). The shapes allow both because I don't know how to choose
- The workflow descriptor may be embedded in the crate or referenced remotely; containers should be pinned by OCI digest.

--


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

## Continuous Integration (GitHub Actions) used to validate the crate

This repo includes `.github/workflows/ci.yml` which:
- Installs `ajv-cli` to validate JSON Schemas
- Installs `pyshacl` to validate SHACL shapes
- Validates the included example crate

The workflow runs on every push and pull request.
