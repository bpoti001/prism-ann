# Algorithm Freeze v3 (ADR-0004 & ADR-0005)

- Frozen at: 2026-11-21T00:26:37Z
- Git HEAD: 6682dfda5c343a5daa8770ab98098e06ca687a02
- Rule: the single Phase 19 confirmatory v3 run must match every SHA-256 hash below. Any edit invalidates confirmatory status.

```
9098e975af1c8c11b8925adbe290a1660cace716778be04139daaf7ea630233a  src/modules/prism_ann/ubp_resolver.py
b707b2ce00fdfd8e95ba450cbd33ff6fea299072de3bef84adbfa293d16230ff  src/modules/prism_ann_v3/__init__.py
5f82c0da10a8741d0605c6f2ace68edbef404c4aba4a65a4aa04fb5005b13fe3  src/modules/prism_ann_v3/ckernel_bridge.py
d86c351467f84fe5fb14a8189dcd576cb94a740a449b03b418850bff9dbf82ec  src/modules/prism_ann_v3/geometric_hhnsw.py
0f60bee21806260c16b8af5aba0fbdbeb421e00f244eefd8279ad7eb4cd3ca1a  src/modules/prism_ann_v3/index.py
75e26a3c80d133502dd507c4bd21dfafbe0479901e045a7cedf552503c3ed3bb  src/modules/prism_ann_v3/trimodal_v3.py
14ee25cbe4e52f1eb9ec97e45ec6c68754390ac77da5ea483a415873e2b30b92  bench/prism_ckernel.cpp
```
