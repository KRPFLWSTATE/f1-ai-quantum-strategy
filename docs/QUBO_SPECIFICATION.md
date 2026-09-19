# QUBO / Ising specification (Stage 4)

Version: **1.0.0**. Gate C only. No QAOA circuits, mixers, angle fitting, or provider submission.

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

Expanded with `x^2 = x`. No additional pairwise hard prohibitions are encoded in Stage 4 (double-stack is a soft pair cost).

## Penalty proof

For each encoded instance:

- `B` = sum of absolute unpenalised nonconstant QUBO coefficients after centring
- `v_min = 1` for the one-hot binary violation measure `(Σx - 1)^2` on each block
- margin `> 0` (default 1.0)
- `M = B / v_min + margin` (**strict**: `M > B/v_min`)
- at least one feasible bit string exists
- `P(x) = 0` on every feasible state; `P(x) ≥ v_min · M` on every infeasible state
- exhaustive small-n verification: no infeasible state beats the best feasible energy

`B = 0`, empty menus, one-action menus, ties, and negative pair terms are handled explicitly. An adversarial weak `M` fixture demonstrates failure of an unjustified penalty while the derived `M` passes.

Store both the decision objective and the penalised energy. Never compare physical seconds after dropping the offset.

## Ising map

```text
x = (1 - Z) / 2
```

with `Z = +1` for bit 0 and `Z = -1` for bit 1. Record constant, `h_i`, upper `J_ij`, bit/sign convention, and variable order. Verify QUBO and Ising energies for every bit string on small fixtures.

## Scale `s_Q` (for future circuits; no circuit in Stage 4)

```text
s_Q = max(1, max_i |h_i|, max_{i<j} |J_ij|)
```

in the fixed seconds convention, excluding the constant but including hard penalties. Scaling by `s_Q` and undoing it restores energy differences / physical decision margins.

## Decoding

Decode only states satisfying all hard constraints. Return explicit infeasibility reasons otherwise. Deterministic tie handling retains the full set of tolerance-tied optimal legal plans.
