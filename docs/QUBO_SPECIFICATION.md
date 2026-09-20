# QUBO / Ising specification (Stage 4.2)

Version: **1.2.0** (enclosing formulation/spec identity; algebraic conventions unchanged). Gate C only. No QAOA circuits, mixers, angle fitting, or provider submission.

The QUBO encodes the **analytical proxy** coefficients from the Stage 4.2 compiler. It is not the simulator evaluator and not race truth. Coefficients regenerate under repaired in-pit residual and pair-interval costs.

## Variables

One binary `x(c,a)` per retained action. Exactly one selected action per car (one-hot). Stable variable order: all car-1 actions, then car-2 actions. Mapping is reversible.

## Convention

```text
E_Q(x) = offset + sum_{i <= j} Q[i,j] x_i x_j
```

with strictly upper-triangular serialisation plus diagonal, `x_i ∈ {0,1}`, no implicit double counting.

Unpenalised content (centred): unary coefficients on the diagonal; cross-car pair terms in the upper triangle.

## One-hot penalties

```text
M * (sum_a x(1,a) - 1)^2
M * (sum_b x(2,b) - 1)^2
```

Expanded with `x^2 = x`. No additional pairwise hard prohibitions are encoded (double-stack is a soft pair cost).

## Penalty proof

For each encoded instance:

- `B` = sum of absolute unpenalised nonconstant QUBO coefficients after centring
- `v_min = 1` for the one-hot binary violation measure `(Σx - 1)^2` on each block
- margin `> 0` (default 1.0)
- `M = B / v_min + margin` (**strict**: `M > B/v_min`)
- at least one feasible bit string exists
- `P(x) = 0` on every feasible state; `P(x) ≥ v_min · M` on every infeasible state
- exhaustive small-n verification: no infeasible state beats the best feasible energy

## Ising map

```text
x = (1 - Z) / 2
```

with scale restoration checked against the direct objective.
