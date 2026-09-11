# REAMP — Global AI Agent Operating Contract

## Project

Build a production-oriented, research-grade:

**Renewable Energy Asset Intelligence and Management Framework (REAMP)**

The framework shall support heterogeneous renewable-energy assets, initially Solar PV and subsequently Wind, BESS and hybrid renewable-energy systems.

The objective is NOT to build merely a SCADA dashboard.

The objective is to create a reusable framework integrating:

- asset lifecycle management
- IoT/SCADA integration
- edge/fog computing
- data quality management
- asset health assessment
- performance intelligence
- anomaly detection
- predictive maintenance
- risk assessment
- financial impact analysis
- digital-twin capabilities
- cybersecurity
- governance
- explainable AI
- human-in-the-loop decision support
- scalable cloud/edge deployment

---

## NON-NEGOTIABLE DEVELOPMENT RULES

### Rule 1 — Phase discipline

Work ONLY on the current phase.

Do not implement functionality belonging to future phases unless it is required as an architectural dependency.

Do not skip phases.

Do not silently redefine requirements.

If a requirement is ambiguous, identify the ambiguity and resolve it using the project's established design principles before implementation.

---

### Rule 2 — Inspect before modifying

Before changing anything:

1. inspect the repository;
2. identify existing architecture;
3. identify existing code;
4. identify existing tests;
5. identify configuration;
6. identify dependencies;
7. identify documentation;
8. identify unfinished work;
9. determine whether the requested functionality already exists.

Never recreate existing functionality unnecessarily.

---

### Rule 3 — Evidence over assumptions

Do not invent:

- standards
- protocols
- APIs
- scientific claims
- datasets
- benchmark results
- hardware specifications
- citations
- regulatory requirements
- performance numbers.

If external evidence is required, explicitly research and record the source.

Distinguish:

- verified fact
- engineering assumption
- proposed design
- experimental result
- future work.

---

### Rule 4 — Architecture before implementation

For every significant capability:

**Requirement → Design → Interface → Data Model → Implementation → Test → Documentation**

Do not begin with code when the underlying design has not been established.

---

### Rule 5 — Production quality

Code must be:

- modular
- typed where appropriate
- testable
- observable
- secure by design
- configurable
- documented
- maintainable
- deployable.

Avoid unnecessary complexity and premature microservices.

Use modular architecture first. Introduce distributed services only when justified.

---

### Rule 6 — Backward compatibility

Never break an already validated capability without explicitly identifying:

- what is being changed;
- why;
- what depends on it;
- how regression will be prevented.

Run the existing test suite after significant changes.

---

### Rule 7 — Data integrity

Never allow invalid, missing, stale or low-confidence telemetry to be silently treated as trustworthy data.

The framework must distinguish:

- value
- timestamp
- source
- quality
- confidence
- availability
- communication status.

---

### Rule 8 — AI safety and explainability

AI/ML outputs must not be presented as unquestionable truth.

Every important AI result should support:

- confidence;
- evidence/features;
- model/version;
- timestamp;
- explanation where feasible;
- human review where operationally appropriate.

---

### Rule 9 — No fake completion

Never claim:

- "implemented"
- "tested"
- "validated"
- "production-ready"
- "research validated"

unless evidence exists in the repository or test output.

---

## REQUIRED PHASE COMPLETION REPORT

At the end of every phase produce:

### 1. Executive Summary

What was achieved.

### 2. Requirements Implemented

List each completed requirement.

### 3. Repository Changes

List created, modified and deleted files.

### 4. Architecture Impact

Explain architectural changes.

### 5. Tests

Report:

- tests executed
- tests passed
- tests failed
- coverage where available

### 6. Validation Evidence

Provide concrete evidence.

### 7. Known Limitations

List unresolved issues.

### 8. Technical Debt

Record deferred work.

### 9. Next Phase Readiness

Explicitly state:

`READY`

or

`NOT READY`

Do not proceed to the next phase unless the current phase passes its quality gate.

---

## Definition of Done

A phase is complete only when:

- required artefacts exist;
- implementation matches the approved design;
- automated tests exist where applicable;
- existing tests remain functional;
- documentation has been updated;
- security implications have been considered;
- no major unresolved architectural contradiction exists;
- acceptance criteria have been evaluated;
- completion evidence has been recorded.

---

## Preferred Engineering Philosophy

Prefer:

**simple → modular → observable → testable → extensible**

over:

**complex → distributed → speculative → difficult to validate**

The framework should evolve incrementally.

Do not optimise prematurely.

Do not introduce AI merely because AI is available.

Every algorithm must have a measurable purpose.
