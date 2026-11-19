# Experiment Protocol H4: Zero-Write Document Revocation Throughput

- **Governing ADR**: `ADR-0001`
- **Mapped Theorem**: Corollary 1
- **Status**: `PRE_REGISTERED`

## 1. Hypothesis & Mechanistic Prediction
Revoking access to $1{,}000$ documents ($150{,}000$ chunks) via structural edge deletion in SpiceDB under UBP requires $O(1)$ graph mutations ($< 2\text{ ms}$, $0$ vector payload writes), whereas flat ACL-stamped vector payloads require $150{,}000$ vector record updates ($> 4{,}000\text{ ms}$).
