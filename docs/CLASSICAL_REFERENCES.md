# Classical references (Stage 4.2)

Version: **1.2.0**. Independent of the QUBO optimiser as their core. Free/open-source only (NumPy, SciPy/HiGHS). These references agree with the **analytical proxy**; the simulator evaluator is a separate modelled diagnostic and is not race truth.

## A. Vectorised legal enumeration

Enumerate the `K1 × K2` legal plan table — **not** `2^(K1+K2)` invalid bit strings. NumPy broadcasting builds

```text
table[i,j] = C + u1[i] + u2[j] + v[i,j]
```

Returns exact proxy minimum, all tolerance-tied minimisers, gap to next distinct value, legal action count, table-construction time, scan time, memory estimate, and deterministic result hash.

When exact enumeration completes within operational deadlines, it is labelled an **operational classical competitor**, not hidden as an offline-only reference.

## B. Independent MILP

Built separately from the QUBO builder via `scipy.optimize.milp` (HiGHS). Binary `x_a`, `y_b`, product `z_ab` with one-hot and McCormick product constraints. Objective compared to enumeration including selected-pair membership in the minimiser set.

## C. Restricted DP / analytical reference

Exact only when all pair terms are identically zero. Otherwise records `exact_under_assumption=false`.

## D. Practical classical candidates

Uniform random, annealing-style local search, and greedy local improvement — with exact evaluation and timing accounting (compile vs scan vs milp separated). Heuristic headroom relative to exact enumeration is reported; zero headroom blocks Gate E / Stage 5 superiority design claims.
