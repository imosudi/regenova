# REAMP AI Decision Record Specification

## 1. Overview & Regulatory Imperative

The EU Artificial Intelligence Act (Article 12: Record-Keeping and Article 14: Human Oversight) and IEEE 730 Software Quality Assurance standards require that AI systems deployed in high-risk critical infrastructure produce comprehensive, immutable decision records.

In REAMP, an AI model (such as an Isolation Forest anomaly detector, a Weibull degradation estimator, or a predictive work order generator) **never** operates as an opaque black box.

Every consequential algorithmic recommendation generates a canonical **AI Decision Record** tracing the unbroken lineage from input telemetry to physical human authorization:
$$\text{Input Data} \to \text{Model} \to \text{Model Version} \to \text{Output} \to \text{Confidence} \to \text{Evidence} \to \text{Recommendation} \to \text{Human Decision}$$

---

## 2. Schema Specification (`AIDecisionRecord`)

| Stage | Field Name | Type | Description |
| :--- | :--- | :--- | :--- |
| **1** | `input_data_summary` | `Dict[str, Any]` | Summary of input telemetry channels, timestamps, and quality flags. |
| **2** | `model_name` | `str` | Model identifier (e.g. `reamp-cbm-inverter-thermal`). |
| **3** | `model_version` | `str` | Semantic version string (e.g. `1.4.2`). |
| **3** | `model_digest` | `str` | SHA-256 cryptographic digest of model code and trained weights. |
| **4** | `raw_output` | `Dict[str, Any]` | Raw mathematical outputs ($P_f$, RUL hours, anomaly scores). |
| **5** | `confidence` | `float` | Evaluated confidence score $[0.0, 1.0]$. |
| **6** | `evidence_features` | `Dict[str, float]`| Mathematical factor importances summing to $1.0$ (e.g. $\Delta T: 0.52$). |
| **7** | `ai_recommendation` | `str` | Natural-language prescriptive maintenance instruction. |
| **8** | `human_decision` | `str` | `APPROVED`, `REJECTED`, or `MODIFIED`. |
| **8** | `human_actor_id` | `Optional[str]` | User ID of the authorizing Chief Engineer or O&M Director. |
| **8** | `decision_timestamp` | `Optional[str]` | ISO 8601 UTC timestamp of human decision. |
| **8** | `decision_notes` | `Optional[str]` | Human operator notes, modifications, or rejection justifications. |

---

## 3. Sample Serialized AI Decision Record

```json
{
  "decision_id": "AIDEC-20260911-0042",
  "timestamp": "2026-09-11T20:40:00Z",
  "asset_id": "INV-WEST-01",
  "provenance_chain_id": "PROV-NODE-8819",
  "input_data_summary": {
    "telemetry_window_start": "2026-09-11T20:00:00Z",
    "telemetry_window_end": "2026-09-11T20:30:00Z",
    "irradiance_avg_w_m2": 820.5,
    "temperature_heatsink_avg_c": 64.2,
    "quality_status": "VALID_HIGH_CONFIDENCE"
  },
  "model_name": "reamp-cbm-inverter-thermal",
  "model_version": "v1.4.2",
  "model_digest": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "raw_output": {
    "predicted_rul_hours": 720.0,
    "failure_probability_30d": 0.28,
    "priority_score": 79.5
  },
  "confidence": 0.92,
  "evidence_features": {
    "temperature_residual_delta_t": 0.52,
    "ambient_temperature_stress": 0.28,
    "operating_hours_on_fan": 0.20
  },
  "ai_recommendation": "Inspect and replace secondary cooling fan FAN-48V-DC-120MM within 14 days.",
  "human_decision": "APPROVED",
  "human_actor_id": "USR-ENG-01 (Lead Eng. Sarah Chen)",
  "decision_timestamp": "2026-09-11T20:42:15Z",
  "decision_notes": "Confirmed elevated delta-T trend under 85% load. Approved for dispatch."
}
```
