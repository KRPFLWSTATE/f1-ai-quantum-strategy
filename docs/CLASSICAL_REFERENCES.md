> Stage 4.1 repair supersedes Stage 4 Gate C software/evidence claims for action semantics, pair timing, evaluator legality, accounting, and packaging. QUBO algebra conventions remain; numerical coefficients regenerate under repaired costs.

# Classical references (Stage 4)

Version: **1.0.0**. Independent of the QUBO optimiser as their core. Free/open-source only (NumPy, SciPy/HiGHS).

## A. Vectorised legal enumeration

Enumerate the `K1 × K2` legal plan table — **not** `2^(K1+K2)` invalid bit strings. NumPy broadcasting builds

```text
table[i,j] = C + u1[i] + u2[j] + v[i,j]
```

Returns exact proxy minimum, all tolerance-tied minimisers, gap to next distinct value, legal action count, table-construction time, scan time, memory estimate, and deterministic result hash.

When exact enumeration completes within operational deadlines, it is labelled an **operational classical competitor**, not hidden as an offline-only reference.

## B. Independent MILP

Built separately from the QUBO builder via `scipy.optimize.milp` (HiGHS). Binary `x_a`, `y_b`, product `z_ab` with:

```text
sum_a x_a = 1
sum_b y_b = 1
z_ab <= x_a
z_ab <= y_b
z_ab >= x_a + y_b - 1
```

Objective: uncentred physical `C` absorbed outside the solver linear form; value compared as `C + fun`. Record status, solve time, selected plans, and comparison tolerance. No coefficient scaling required on Stage 4 fixtures (max rounding error 0).

Licences: SciPy / HiGHS are free and open-source. No paid solver.

## C. Restricted DP / analytical reference

When all pair terms are identically zero (within tolerance), solve each car independently and combine minima. Exact **only** under that assumption. When pair interactions are nonzero, the method records `exact_under_assumption=false` and does not claim exactness.

## D. Practical classical candidates

All use the same direct proxy scorer and always retain a legal incumbent:

- greedy unary construction + one-car-at-a-time local improvement
- uniform legal sampling (seeded)
- seeded simulated annealing over legal joint plans

Expose evaluation budgets, seeds, and wall accounting. These are development implementations for later fair comparison — **not** Stage 4 performance claims.

## Headroom reporting

```text
heuristic_proxy_headroom = f(greedy_incumbent) - f(exact_proxy_optimum)
exact_reference_headroom = 0
```

If exact enumeration eliminates proxy headroom across the admitted development domain, report that plainly (Gate E warning). Do not manufacture difficulty by enumerating invalid bit strings.
