# Algorithm & Audit Kernel Freeze v3.1 (ADR-0004 & ADR-0005)

- Frozen at: 2026-11-22T22:29:15-06:00
- Git HEAD: 05cbb99f472b5cb3110448593464f39225350cc0
- Rule: Every file in `FREEZE_v3.md` (7/7) plus `bench/prism_audit_kernel.cpp` (8/8) must match these exact SHA-256 hashes before executing `bench/run_reviewer_audit_v3_1.py`.

```
9098e975af1c8c11b8925adbe290a1660cace716778be04139daaf7ea630233a  src/modules/prism_ann/ubp_resolver.py
b707b2ce00fdfd8e95ba450cbd33ff6fea299072de3bef84adbfa293d16230ff  src/modules/prism_ann_v3/__init__.py
5f82c0da10a8741d0605c6f2ace68edbef404c4aba4a65a4aa04fb5005b13fe3  src/modules/prism_ann_v3/ckernel_bridge.py
d86c351467f84fe5fb14a8189dcd576cb94a740a449b03b418850bff9dbf82ec  src/modules/prism_ann_v3/geometric_hhnsw.py
0f60bee21806260c16b8af5aba0fbdbeb421e00f244eefd8279ad7eb4cd3ca1a  src/modules/prism_ann_v3/index.py
75e26a3c80d133502dd507c4bd21dfafbe0479901e045a7cedf552503c3ed3bb  src/modules/prism_ann_v3/trimodal_v3.py
14ee25cbe4e52f1eb9ec97e45ec6c68754390ac77da5ea483a415873e2b30b92  bench/prism_ckernel.cpp
e7a1bad7d7708d385314165c4dda36604dfc280ad58c167668ea87cae680d092  bench/prism_audit_kernel.cpp
```
