# PCL Exchange proposal using RO-Crate Profile, Schemas, and Shapes

This repository captures a minimal, interoperable **PCL-to-PCL exchange** pattern using:
- **RO-Crate** as the packaging and JSON-LD context carrier
- **JSON Schema** for validating the *envelope* and *error contract*
- **SHACL** shapes for validating content nodes for measurement requests and workflow launches

## Layout

```
.
├── README.md
├── schemas/
│   ├── envelope.json          # JSON Schema — PCLActionEnvelope (Draft 2020-12)
│   └── error.json             # JSON Schema — PCLError (tiny error contract)
├── shapes/
│   ├── measurement_request.ttl  # SHACL — pcl:MeasurementRequestShape
│   └── workflow_launch.ttl      # SHACL — pcl:WorkflowLaunchShape
├── examples/
│   └── pcl_action_crate_example.json  # Example RO-Crate JSON-LD graph
└── docs/
    └── conversation_verbatim.md  # Full verbatim answers used to generate this repo
```

## Validating

- **Envelope**:
  - Validate with JSON Schema: `schemas/envelope.json`
- **Error (nack) contract**:
  - Validate with JSON Schema: `schemas/error.json`
- **Content**:
  - Validate measurement requests against `shapes/measurement_request.ttl`
  - Validate workflow launches against `shapes/workflow_launch.ttl`

## Notes
- The RO-Crate profile identifier is assumed to be `https://w3id.org/pcl-profile/action/v1`. Adjust as needed.
- Units may be expressed via `schema:unitText` (free text) or `qudt:unit` (preferred). The shapes allow both to enable gradual adoption.
- The workflow descriptor may be embedded in the crate or referenced remotely; containers should be pinned by OCI digest.

---

Generated on 2025-10-25T08:32:14.569017Z.

## Quickstart (local)

```bash
# Optional: create and activate a virtual environment for Python tools
python3 -m venv .venv && source .venv/bin/activate

# Install tools and run validations
make install
make validate
```

## Make it a real Git repo and push to GitHub

```bash
# From inside the project directory after unzipping:
git init
git add .
git commit -m "Initial commit: PCL Exchange profile, schemas, shapes, and CI"

# Create a new GitHub repository (replace <ORG_OR_USER> and repo name as desired)
# Option A: via GitHub CLI (recommended)
gh repo create <ORG_OR_USER>/pcl-exchange --public --source=. --remote=origin --push

# Option B: manual remote setup (if you don't use gh CLI)
# 1) Create an empty repo on GitHub named pcl-exchange
# 2) Then set the remote and push:
git remote add origin git@github.com:<ORG_OR_USER>/pcl-exchange.git
git branch -M main
git push -u origin main
```

### Requirements
- Node.js (for ajv-cli) and Python 3.9+ (for pyshacl)
- Optional: GitHub CLI (`brew install gh`) for one-command repo creation
- SSH keys set up for GitHub or HTTPS credentials

## Continuous Integration (GitHub Actions)

This repo includes `.github/workflows/ci.yml` which:
- Installs `ajv-cli` to validate JSON Schemas
- Installs `pyshacl` to validate SHACL shapes
- Validates the included example crate

The workflow runs on every push and pull request.
