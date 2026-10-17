"""Compiled post-commitment continuation.

The scalar ``RaceEngine`` is unchanged and remains the default. This module is
selected only through ``f1q.a4.backend_select``. Numeric kernels are compiled
with ``fastmath`` disabled so contracted floating-point reassociation is not
enabled.

The kernel covers ``continue_to_finish`` after a checkpoint. Commitment,
arrival, and the short pre-commit advance stay on the scalar engine, which is
where those decisions are made. Unsupported states return a status instead of
silently finishing on the scalar loop.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from numba import njit

from f1q.simulator.engine import BIG, EPS, OVERTAKE_ORDER_SNAP_LAPS

KERNEL_VERSION = "compiled-event-loop-1"
_NJIT = dict(fastmath=False, error_model="python")

# Schedule kinds. Name ranks follow lexicographic kind strings.
S_CATCH = 1
S_LAP = 2
S_PIT_ENTRY = 3
S_PIT_TIMER = 4
S_REGIME = 5
S_SC = 6
_NAME_RANK = np.array([0, 0, 1, 2, 3, 4, 5], dtype=np.int64)

# Log kinds.
L_LAP = 1
L_LAP_SNAP = 2
L_FINISH = 3
L_REGIME = 4
L_SC = 5
L_PIT_ENTRY = 6
L_PIT_WAIT = 7
L_SERVICE = 8
L_SERVICE_AFTER = 9
L_SERVICE_DONE = 10
L_PIT_EXIT = 11
L_OVERTAKE = 12
L_OVERTAKE_TICK = 13
L_LEADER = 14
L_EXPIRED = 15

PH_NONE = 0
PH_IN = 1
PH_WAIT = 2
PH_SERVICE = 3
PH_OUT = 4

PK_CONT = 1
PK_PIT = 2
PK_DELAY = 3

RG_GREEN = 0
RG_SC = 1
RG_VSC = 2

ST_OK = 0
ST_FUEL = 1
ST_STEPS = 2
ST_OVERFLOW = 4
ST_STACK = 5
ST_TYRE = 6
ST_UNSUPPORTED = 7

_COMPOUND = {"soft": 0, "medium": 1, "hard": 2}
_COMPOUND_NAME = ("soft", "medium", "hard")


@njit(**_NJIT)
def _free_lap(green, offset, age, form_linear, wear, curv, fuel, time_scale, curve_scale, time_per_kg):
    linear = wear * time_scale * age
    if form_linear == 1:
        tyre = linear
    else:
        tyre = linear + curv * curve_scale * age * age
    return green + offset + tyre + time_per_kg * fuel


@njit(**_NJIT)
def _pace(green, offset, age, form_linear, wear, curv, fuel, time_scale, curve_scale, time_per_kg, kg_per_lap):
    alpha = wear * time_scale
    beta = 0.0 if form_linear == 1 else curv * curve_scale
    gamma = time_per_kg
    a = green + offset + alpha * age + beta * age * age + gamma * fuel
    b = alpha + 2.0 * beta * age - gamma * kg_per_lap
    c = beta
    return a, b, c


@njit(**_NJIT)
def _time_to_cover(a, b, c, ds):
    if ds <= EPS:
        return 0.0
    return max(0.0, a * ds + 0.5 * b * ds * ds + (c / 3.0) * ds ** 3)


@njit(**_NJIT)
def _distance_in_time(a, b, c, dt):
    if dt <= EPS:
        return 0.0
    ds = dt / max(a, EPS)
    for _ in range(12):
        residual = (c / 3.0) * ds ** 3 + 0.5 * b * ds * ds + a * ds - dt
        deriv = c * ds * ds + b * ds + a
        if abs(deriv) < 1e-18:
            break
        ds -= residual / deriv
        if ds < 0.0:
            ds = 0.0
            break
    return max(ds, 0.0)


@njit(**_NJIT)
def _car_distance(i, in_pit, phase, completed, frac, entry_completed, entry_frac, frozen, has_frozen, pstart, pend, pclock):
    if in_pit[i] == 0:
        return float(completed[i]) + frac[i]
    entry_c = entry_completed[i]
    efrac = entry_frac[i]
    entry_progress = float(entry_c) + efrac
    box_progress = float(entry_c) + 1.0
    if phase[i] == PH_IN:
        start_t = pstart[i]
        end_t = pend[i]
        now_t = pclock[i]
        if (not math.isnan(start_t)) and (not math.isnan(end_t)) and (not math.isnan(now_t)) and end_t > start_t + EPS:
            alpha = (now_t - start_t) / (end_t - start_t)
            if alpha < 0.0:
                alpha = 0.0
            if alpha > 1.0:
                alpha = 1.0
            return entry_progress + alpha * (box_progress - entry_progress)
        frozen_frac = frozen[i] if has_frozen[i] == 1 else efrac
        return float(completed[i]) + frozen_frac
    frozen_frac = frozen[i] if has_frozen[i] == 1 else 0.0
    return float(completed[i]) + frozen_frac


@njit(**_NJIT)
def _push(n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, t, k, c, i0, i1, f0, f1):
    i = n_ev[0]
    if i >= ev_t.shape[0]:
        return ST_OVERFLOW
    ev_t[i] = t
    ev_k[i] = k
    ev_c[i] = c
    ev_i0[i] = i0
    ev_i1[i] = i1
    ev_f0[i] = f0
    ev_f1[i] = f1
    n_ev[0] = i + 1
    return ST_OK


@njit(**_NJIT)
def _sort_order(idx, n, dist, rank):
    for i in range(1, n):
        j = i
        while j > 0:
            a = idx[j - 1]
            b = idx[j]
            swap = dist[b] > dist[a] or (dist[b] == dist[a] and rank[b] < rank[a])
            if not swap:
                break
            idx[j - 1] = b
            idx[j] = a
            j -= 1


@njit(**_NJIT)
def _count_bits(mask):
    n = 0
    for b in range(3):
        if (mask & (1 << b)) != 0:
            n += 1
    return n


@njit(**_NJIT)
def _used_mask(i, compound, inv_used, inv_compound, nsets, used_extra):
    mask = used_extra[i]
    mask |= 1 << compound[i]
    for s in range(nsets[i]):
        if inv_used[i, s] == 1:
            mask |= 1 << inv_compound[i, s]
    return mask


@njit(**_NJIT)
def _select_set(i, compound, inv_used, inv_compound, nsets, used_extra):
    mask = _used_mask(i, compound, inv_used, inv_compound, nsets, used_extra)
    for s in range(nsets[i]):
        if inv_used[i, s] == 1:
            continue
        comp = inv_compound[i, s]
        if (mask & (1 << comp)) == 0:
            return comp, s
    for s in range(nsets[i]):
        if inv_used[i, s] == 0:
            return inv_compound[i, s], s
    return -1, -1


@njit(**_NJIT)
def run_continuation(
    n,
    max_steps,
    max_sets,
    completed,
    frac,
    in_pit,
    phase,
    compound,
    tyre_age,
    fuel_a,
    fuel_e,
    pit_this,
    retired,
    has_finish,
    finish_time,
    speed,
    want_pass,
    pending_c,
    pending_s,
    pstart,
    pend,
    pclock,
    entry_completed,
    entry_frac,
    frozen,
    has_frozen,
    service_wait,
    team,
    nsets,
    mounted,
    inv_compound,
    inv_used,
    inv_age,
    used_extra,
    policy_kind,
    policy_delay,
    policy_ref,
    policy_c,
    policy_s,
    car_rank,
    crew,
    n_ev,
    ev_t,
    ev_k,
    ev_c,
    ev_i0,
    ev_i1,
    ev_f0,
    ev_f1,
    t_box,
    finished,
    regime,
    regime_end,
    has_regime_end,
    leader_finished,
    leader_finish_t,
    leader_car,
    horizon,
    required,
    green,
    form_linear,
    wear,
    curv,
    offsets0,
    offsets1,
    offsets2,
    time_scale,
    curve_scale,
    time_per_kg,
    kg_per_lap,
    min_gap_s,
    attack_s,
    adv_need,
    sc_factor,
    vsc_factor,
    sc_catch,
    sc_queue_gap,
    dt_green,
    dt_regime,
    entry,
    exit_f,
    box_frac,
    t_in,
    t_service,
    t_out,
    stacking_forbidden,
    prio_catch,
    prio_lap,
    prio_pit_entry,
    prio_pit_timer,
    prio_regime,
    prio_sc,
    race_rank,
):
    offsets = np.empty(3, dtype=np.float64)
    offsets[0] = offsets0
    offsets[1] = offsets1
    offsets[2] = offsets2
    dist = np.empty(n, dtype=np.float64)
    order = np.empty(n, dtype=np.int64)
    bt = np.empty(n * 4 + 4, dtype=np.float64)
    bp = np.empty(n * 4 + 4, dtype=np.int64)
    bk = np.empty(n * 4 + 4, dtype=np.int64)
    bc = np.empty(n * 4 + 4, dtype=np.int64)
    ba = np.empty(n * 4 + 4, dtype=np.int64)
    br = np.empty(n * 4 + 4, dtype=np.int64)
    bn = np.empty(n * 4 + 4, dtype=np.int64)
    fk = np.empty(n * 4 + 4, dtype=np.int64)
    fc = np.empty(n * 4 + 4, dtype=np.int64)
    fa = np.empty(n * 4 + 4, dtype=np.int64)
    steps = 0
    while finished[0] == 0:
        steps += 1
        if steps > max_steps:
            return ST_STEPS
        t = t_box[0]
        # snap boundaries
        for i in range(n):
            if in_pit[i] == 1 or retired[i] == 1 or has_finish[i] == 1:
                continue
            if frac[i] >= 1.0 - 1e-9:
                completed[i] = completed[i] + 1
                frac[i] = 0.0
                st = _push(n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, t, L_LAP_SNAP, i, completed[i], 0, 0.0, 0.0)
                if st != ST_OK:
                    return st
            elif frac[i] < 0.0:
                frac[i] = 0.0
        # intents
        for i in range(n):
            if policy_kind[i] == PK_CONT or policy_kind[i] == 0:
                if in_pit[i] == 1 and (pending_c[i] >= 0 or pending_s[i] >= 0):
                    policy_kind[i] = PK_CONT
                    continue
                policy_kind[i] = PK_CONT
                remaining = horizon - completed[i]
                intent_pit = 0
                ic = -1
                iset = -1
                if remaining > 0:
                    mask = _used_mask(i, compound, inv_used, inv_compound, nsets, used_extra)
                    if _count_bits(mask) < required:
                        ic, iset = _select_set(i, compound, inv_used, inv_compound, nsets, used_extra)
                        if ic < 0:
                            return ST_TYRE
                        intent_pit = 1
            else:
                if policy_kind[i] == PK_DELAY and policy_ref[i] < 0:
                    policy_ref[i] = completed[i]
                intent_pit = 0
                ic = -1
                iset = -1
                if policy_kind[i] == PK_PIT:
                    intent_pit = 1
                    ic = policy_c[i]
                    iset = policy_s[i]
                elif policy_kind[i] == PK_DELAY:
                    if policy_delay[i] != 1 and policy_delay[i] != 2:
                        return ST_UNSUPPORTED
                    if completed[i] - policy_ref[i] >= policy_delay[i]:
                        intent_pit = 1
                        ic = policy_c[i]
                        iset = policy_s[i]
            if intent_pit == 1:
                missed = in_pit[i] == 0 and retired[i] == 0 and has_finish[i] == 0 and frac[i] > entry + EPS
                if missed:
                    pit_this[i] = 0
                    if in_pit[i] == 0:
                        pending_c[i] = -1
                        pending_s[i] = -1
                    policy_kind[i] = PK_CONT
                    st = _push(n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, t, L_EXPIRED, i, 0, 0, frac[i], 0.0)
                    if st != ST_OK:
                        return st
                    continue
                pit_this[i] = 1
                if ic < 0 or iset < 0:
                    ic, iset = _select_set(i, compound, inv_used, inv_compound, nsets, used_extra)
                    if ic < 0:
                        return ST_TYRE
                pending_c[i] = ic
                pending_s[i] = iset
            elif in_pit[i] == 0:
                pit_this[i] = 0
        # speeds
        for i in range(n):
            want_pass[i] = -1
            if in_pit[i] == 1 or retired[i] == 1 or has_finish[i] == 1:
                speed[i] = 0.0
                continue
            off = offsets[compound[i]]
            ft = _free_lap(green, off, tyre_age[i], form_linear, wear, curv, fuel_a[i], time_scale, curve_scale, time_per_kg)
            speed[i] = 1.0 / max(ft, EPS)
        t_sc = sc_factor * green
        t_vsc = vsc_factor * green
        v_sc = 1.0 / t_sc
        v_vsc = 1.0 / t_vsc
        v_catch = 1.0 / (sc_catch * t_sc)
        target_sc = sc_queue_gap / t_sc
        n_ord = 0
        for i in range(n):
            if in_pit[i] == 0 and has_finish[i] == 0:
                dist[i] = _car_distance(i, in_pit, phase, completed, frac, entry_completed, entry_frac, frozen, has_frozen, pstart, pend, pclock)
                order[n_ord] = i
                n_ord += 1
        _sort_order(order, n_ord, dist, car_rank)
        if regime[0] == RG_VSC:
            for j in range(n_ord):
                i = order[j]
                if speed[i] > v_vsc:
                    speed[i] = v_vsc
        if regime[0] == RG_SC and n_ord > 0:
            i0 = order[0]
            if speed[i0] > v_sc:
                speed[i0] = v_sc
        for j in range(1, n_ord):
            i = order[j]
            ahead = order[j - 1]
            gap = dist[ahead] - dist[i]
            t_ahead = 1.0 / max(speed[ahead], EPS)
            time_gap = gap * t_ahead
            if regime[0] == RG_SC:
                if gap > target_sc + EPS:
                    if speed[i] > v_catch:
                        speed[i] = v_catch
                else:
                    if speed[i] > speed[ahead]:
                        speed[i] = speed[ahead]
                continue
            min_laps = min_gap_s / max(t_ahead, EPS)
            if regime[0] == RG_VSC:
                if gap < min_laps - EPS and speed[i] > speed[ahead]:
                    speed[i] = speed[ahead]
                continue
            off_a = offsets[compound[ahead]]
            off_i = offsets[compound[i]]
            ft_a = _free_lap(green, off_a, tyre_age[ahead], form_linear, wear, curv, fuel_a[ahead], time_scale, curve_scale, time_per_kg)
            ft_i = _free_lap(green, off_i, tyre_age[i], form_linear, wear, curv, fuel_a[i], time_scale, curve_scale, time_per_kg)
            advantage = ft_a - ft_i
            if advantage >= adv_need and time_gap <= attack_s:
                want_pass[i] = ahead
            elif gap < min_laps - EPS and speed[i] > speed[ahead]:
                speed[i] = speed[ahead]
        # next events
        nb = 0

        def _prio(kind):
            if kind == S_CATCH:
                return prio_catch
            if kind == S_LAP:
                return prio_lap
            if kind == S_PIT_ENTRY:
                return prio_pit_entry
            if kind == S_PIT_TIMER:
                return prio_pit_timer
            if kind == S_REGIME:
                return prio_regime
            return prio_sc

        def _add(dt, kind, car, ahead_i):
            nonlocal nb
            if dt < 0.0 or dt > BIG / 4.0:
                return
            if 0.0 <= dt < 1e-12:
                dt = 0.0
            if nb >= bt.shape[0]:
                return
            bt[nb] = t + max(dt, 0.0)
            bp[nb] = _prio(kind)
            bk[nb] = kind
            bc[nb] = car
            ba[nb] = ahead_i
            br[nb] = race_rank if car < 0 else car_rank[car]
            bn[nb] = _NAME_RANK[kind]
            nb += 1

        if regime[0] != RG_GREEN and has_regime_end[0] == 1:
            _add(regime_end[0] - t, S_REGIME, -1, -1)
        for i in range(n):
            if retired[i] == 1 or has_finish[i] == 1:
                continue
            if in_pit[i] == 1:
                if not math.isnan(pend[i]):
                    _add(max(0.0, pend[i] - t), S_PIT_TIMER, i, -1)
                continue
            v = speed[i]
            if v <= EPS:
                continue
            remain_lap = 1.0 - frac[i]
            if remain_lap <= 1e-9:
                continue
            off = offsets[compound[i]]
            ft = _free_lap(green, off, tyre_age[i], form_linear, wear, curv, fuel_a[i], time_scale, curve_scale, time_per_kg)
            v_free = 1.0 / max(ft, EPS)
            green_free = regime[0] == RG_GREEN and abs(v - v_free) <= 1e-9
            a = 0.0
            b = 0.0
            c = 0.0
            if green_free:
                a, b, c = _pace(green, off, tyre_age[i], form_linear, wear, curv, fuel_a[i], time_scale, curve_scale, time_per_kg, kg_per_lap)
                _add(_time_to_cover(a, b, c, remain_lap), S_LAP, i, -1)
            else:
                _add(remain_lap / v, S_LAP, i, -1)
            if pit_this[i] == 1:
                if frac[i] <= entry + EPS:
                    ds_entry = entry - frac[i]
                else:
                    ds_entry = 1.0 - frac[i] + entry
                if green_free:
                    if ds_entry > 1e-9:
                        _add(_time_to_cover(a, b, c, ds_entry), S_PIT_ENTRY, i, -1)
                    else:
                        _add(0.0, S_PIT_ENTRY, i, -1)
                else:
                    _add(ds_entry / v if ds_entry > 1e-9 else 0.0, S_PIT_ENTRY, i, -1)
        n_ev_ord = 0
        for i in range(n):
            if in_pit[i] == 0 and has_finish[i] == 0 and retired[i] == 0:
                dist[i] = _car_distance(i, in_pit, phase, completed, frac, entry_completed, entry_frac, frozen, has_frozen, pstart, pend, pclock)
                order[n_ev_ord] = i
                n_ev_ord += 1
        _sort_order(order, n_ev_ord, dist, car_rank)
        if regime[0] == RG_SC and n_ev_ord >= 2:
            for j in range(1, n_ev_ord):
                i = order[j]
                ahead = order[j - 1]
                gap = dist[ahead] - dist[i]
                vf = speed[i]
                va = speed[ahead]
                if gap > target_sc + EPS and vf > va + EPS:
                    _add((gap - target_sc) / (vf - va), S_SC, i, ahead)
        if regime[0] == RG_GREEN:
            for j in range(1, n_ev_ord):
                i = order[j]
                ahead = want_pass[i]
                if ahead < 0:
                    continue
                if in_pit[ahead] == 1 or retired[ahead] == 1 or has_finish[ahead] == 1:
                    continue
                vf = speed[i]
                va = speed[ahead]
                gap = dist[ahead] - dist[i]
                if vf > va + EPS and gap > EPS:
                    _add(gap / (vf - va), S_CATCH, i, ahead)
                elif vf > va + EPS and gap <= EPS:
                    _add(0.0, S_CATCH, i, ahead)
        dt_max = dt_green if regime[0] == RG_GREEN else dt_regime
        if nb == 0:
            dt = dt_max
            nf = 0
        else:
            for i in range(1, nb):
                j = i
                while j > 0:
                    swap = False
                    if bt[j] < bt[j - 1]:
                        swap = True
                    elif bt[j] == bt[j - 1] and bp[j] < bp[j - 1]:
                        swap = True
                    elif bt[j] == bt[j - 1] and bp[j] == bp[j - 1] and bn[j] < bn[j - 1]:
                        swap = True
                    elif bt[j] == bt[j - 1] and bp[j] == bp[j - 1] and bn[j] == bn[j - 1] and br[j] < br[j - 1]:
                        swap = True
                    if not swap:
                        break
                    bt_tmp = bt[j - 1]
                    bt[j - 1] = bt[j]
                    bt[j] = bt_tmp
                    bp_tmp = bp[j - 1]
                    bp[j - 1] = bp[j]
                    bp[j] = bp_tmp
                    bk_tmp = bk[j - 1]
                    bk[j - 1] = bk[j]
                    bk[j] = bk_tmp
                    bc_tmp = bc[j - 1]
                    bc[j - 1] = bc[j]
                    bc[j] = bc_tmp
                    ba_tmp = ba[j - 1]
                    ba[j - 1] = ba[j]
                    ba[j] = ba_tmp
                    br_tmp = br[j - 1]
                    br[j - 1] = br[j]
                    br[j] = br_tmp
                    bn_tmp = bn[j - 1]
                    bn[j - 1] = bn[j]
                    bn[j] = bn_tmp
                    j -= 1
            t_next = bt[0]
            dt = t_next - t
            if dt > dt_max:
                dt = dt_max
                nf = 0
            else:
                if dt < 0.0:
                    dt = 0.0
                nf = 0
                for i in range(nb):
                    if abs(bt[i] - t_next) <= 1e-9 and bk[i] != S_LAP:
                        fk[nf] = bk[i]
                        fc[nf] = bc[i]
                        fa[nf] = ba[i]
                        nf += 1
        if dt <= EPS and nf == 0:
            dt = dt_max
        # step motion
        st = _step(n, dt, t, completed, frac, in_pit, phase, compound, tyre_age, fuel_a, fuel_e, retired, has_finish, finish_time, speed, pclock, frozen, has_frozen, n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, t_box, horizon, green, form_linear, wear, curv, offsets, time_scale, curve_scale, time_per_kg, kg_per_lap, regime[0])
        if st != ST_OK:
            return st
        t = t_box[0]
        if nf > 0:
            st = _fire(n, nf, fk, fc, fa, t, completed, frac, in_pit, phase, compound, tyre_age, fuel_a, pit_this, retired, has_finish, finish_time, want_pass, pending_c, pending_s, pstart, pend, pclock, entry_completed, entry_frac, frozen, has_frozen, service_wait, team, nsets, mounted, inv_compound, inv_used, inv_age, used_extra, policy_kind, crew, n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, regime, regime_end, has_regime_end, horizon, green, form_linear, wear, curv, offsets, time_scale, curve_scale, time_per_kg, entry, exit_f, box_frac, t_in, t_service, t_out, stacking_forbidden, adv_need)
            if st != ST_OK:
                return st
        st = _overtakes(n, dt, completed, frac, in_pit, compound, tyre_age, fuel_a, retired, has_finish, speed, want_pass, car_rank, n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, t_box, regime[0], green, form_linear, wear, curv, offsets, time_scale, curve_scale, time_per_kg, adv_need, entry_completed, entry_frac, frozen, has_frozen, phase, pstart, pend, pclock)
        if st != ST_OK:
            return st
        st = _maybe_finish(n, completed, frac, in_pit, phase, retired, has_finish, finish_time, entry_completed, entry_frac, frozen, has_frozen, pstart, pend, pclock, car_rank, n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, t_box, finished, leader_finished, leader_finish_t, leader_car, horizon)
        if st != ST_OK:
            return st
    return ST_OK


@njit(**_NJIT)
def _consume(i, ds, fuel_a, fuel_e, tyre_age, kg_per_lap):
    if abs(ds) <= EPS:
        return ST_OK
    fuel_a[i] -= kg_per_lap * ds
    fuel_e[i] -= kg_per_lap * ds
    tyre_age[i] = max(0.0, tyre_age[i] + ds)
    if fuel_a[i] < -1e-7:
        return ST_FUEL
    return ST_OK


@njit(**_NJIT)
def _step(n, dt, t, completed, frac, in_pit, phase, compound, tyre_age, fuel_a, fuel_e, retired, has_finish, finish_time, speed, pclock, frozen, has_frozen, n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, t_box, horizon, green, form_linear, wear, curv, offsets, time_scale, curve_scale, time_per_kg, kg_per_lap, regime):
    if dt <= EPS:
        t_box[0] = t + max(dt, 0.0)
        for i in range(n):
            if in_pit[i] == 1:
                pclock[i] = t_box[0]
                continue
            if retired[i] == 1 or has_finish[i] == 1:
                continue
            progressed = float(completed[i]) + frac[i]
            if progressed + EPS >= float(horizon):
                completed[i] = horizon
                frac[i] = 0.0
                finish_time[i] = t_box[0]
                has_finish[i] = 1
                st = _push(n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, t_box[0], L_FINISH, i, 0, 0, float(horizon), 0.0)
                if st != ST_OK:
                    return st
        return ST_OK
    for i in range(n):
        if in_pit[i] == 1:
            pclock[i] = t + dt
            continue
        if retired[i] == 1 or has_finish[i] == 1:
            continue
        v = speed[i]
        old = float(completed[i]) + frac[i]
        off = offsets[compound[i]]
        ft = _free_lap(green, off, tyre_age[i], form_linear, wear, curv, fuel_a[i], time_scale, curve_scale, time_per_kg)
        v_free = 1.0 / max(ft, EPS)
        green_free = regime == RG_GREEN and abs(v - v_free) <= 1e-9
        if green_free:
            a, b, c = _pace(green, off, tyre_age[i], form_linear, wear, curv, fuel_a[i], time_scale, curve_scale, time_per_kg, kg_per_lap)
            ds = _distance_in_time(a, b, c, dt)
        else:
            a = 0.0
            b = 0.0
            c = 0.0
            ds = v * dt
        if old + ds >= float(horizon) - EPS:
            ds_used = max(0.0, float(horizon) - old)
            if green_free:
                used_dt = _time_to_cover(a, b, c, ds_used)
            else:
                used_dt = ds_used / v if v > EPS else dt
            st = _consume(i, ds_used, fuel_a, fuel_e, tyre_age, kg_per_lap)
            if st != ST_OK:
                return st
            completed[i] = horizon
            frac[i] = 0.0
            finish_time[i] = t + used_dt
            has_finish[i] = 1
            st = _push(n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, t, L_FINISH, i, 0, 0, float(horizon), 0.0)
            if st != ST_OK:
                return st
            continue
        st = _consume(i, ds, fuel_a, fuel_e, tyre_age, kg_per_lap)
        if st != ST_OK:
            return st
        total = old + ds
        new_completed = int(math.floor(total + 1e-15))
        if new_completed > completed[i]:
            st = _push(n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, t, L_LAP, i, new_completed, 0, 0.0, 0.0)
            if st != ST_OK:
                return st
        completed[i] = new_completed
        frac[i] = total - float(completed[i])
    t_box[0] = t + dt
    for i in range(n):
        if in_pit[i] == 1:
            pclock[i] = t_box[0]
    return ST_OK


@njit(**_NJIT)
def _mount(i, comp, set_i, compound, tyre_age, mounted, inv_compound, inv_used, inv_age, nsets, used_extra):
    if set_i == mounted[i]:
        return ST_UNSUPPORTED
    if set_i < 0 or set_i >= nsets[i]:
        return ST_TYRE
    if inv_compound[i, set_i] != comp:
        return ST_UNSUPPORTED
    if inv_used[i, set_i] == 1 and set_i != mounted[i]:
        return ST_UNSUPPORTED
    inv_used[i, set_i] = 1
    inv_age[i, set_i] = 0.0
    old = mounted[i]
    if 0 <= old < nsets[i]:
        inv_age[i, old] = tyre_age[i]
        inv_used[i, old] = 1
    compound[i] = comp
    mounted[i] = set_i
    tyre_age[i] = 0.0
    used_extra[i] = used_extra[i] | (1 << comp)
    return ST_OK


@njit(**_NJIT)
def _fire(
    n, nf, fk, fc, fa, t, completed, frac, in_pit, phase, compound, tyre_age, fuel_a, pit_this, retired, has_finish, finish_time, want_pass, pending_c, pending_s, pstart, pend, pclock, entry_completed, entry_frac, frozen, has_frozen, service_wait, team, nsets, mounted, inv_compound, inv_used, inv_age, used_extra, policy_kind, crew, n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, regime, regime_end, has_regime_end, horizon, green, form_linear, wear, curv, offsets, time_scale, curve_scale, time_per_kg, entry, exit_f, box_frac, t_in, t_service, t_out, stacking_forbidden, adv_need,
):
    for e in range(nf):
        kind = fk[e]
        i = fc[e]
        if kind == S_REGIME:
            regime[0] = RG_GREEN
            has_regime_end[0] = 0
            regime_end[0] = np.nan
            st = _push(n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, t, L_REGIME, -1, 0, 0, 0.0, 0.0)
            if st != ST_OK:
                return st
            continue
        if kind == S_SC:
            st = _push(n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, t, L_SC, i, fa[e], 0, 0.0, 0.0)
            if st != ST_OK:
                return st
            continue
        if kind == S_PIT_ENTRY and in_pit[i] == 0 and pit_this[i] == 1:
            in_pit[i] = 1
            entry_completed[i] = completed[i]
            entry_frac[i] = entry
            frozen[i] = entry
            has_frozen[i] = 1
            frac[i] = entry
            phase[i] = PH_IN
            pstart[i] = t
            pend[i] = t + t_in
            pclock[i] = t
            pit_this[i] = 0
            if policy_kind[i] == PK_PIT or policy_kind[i] == PK_DELAY:
                policy_kind[i] = PK_CONT
            st = _push(n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, t, L_PIT_ENTRY, i, entry_completed[i], completed[i], t_in, 0.0)
            if st != ST_OK:
                return st
            continue
        if kind == S_PIT_TIMER:
            st = _advance_pit(i, t, completed, frac, phase, compound, tyre_age, pending_c, pending_s, pstart, pend, pclock, entry_completed, frozen, has_frozen, service_wait, team, nsets, mounted, inv_compound, inv_used, inv_age, used_extra, crew, n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, in_pit, box_frac, t_service, t_out, exit_f, stacking_forbidden, entry_frac)
            if st != ST_OK:
                return st
            continue
        if kind == S_CATCH and regime[0] == RG_GREEN and in_pit[i] == 0:
            ahead = fa[e]
            if ahead < 0:
                ahead = want_pass[i]
            if ahead < 0:
                continue
            if in_pit[ahead] == 1 or has_finish[ahead] == 1 or retired[ahead] == 1:
                want_pass[i] = -1
                continue
            off_a = offsets[compound[ahead]]
            off_i = offsets[compound[i]]
            ft_a = _free_lap(green, off_a, tyre_age[ahead], form_linear, wear, curv, fuel_a[ahead], time_scale, curve_scale, time_per_kg)
            ft_i = _free_lap(green, off_i, tyre_age[i], form_linear, wear, curv, fuel_a[i], time_scale, curve_scale, time_per_kg)
            if ft_a - ft_i < adv_need - 1e-9:
                want_pass[i] = -1
                continue
            gap = _car_distance(ahead, in_pit, phase, completed, frac, entry_completed, entry_frac, frozen, has_frozen, pstart, pend, pclock) - _car_distance(i, in_pit, phase, completed, frac, entry_completed, entry_frac, frozen, has_frozen, pstart, pend, pclock)
            if gap > max(OVERTAKE_ORDER_SNAP_LAPS * 10.0, 1e-9):
                want_pass[i] = ahead
                continue
            new_d = _car_distance(ahead, in_pit, phase, completed, frac, entry_completed, entry_frac, frozen, has_frozen, pstart, pend, pclock) + OVERTAKE_ORDER_SNAP_LAPS
            completed[i] = int(math.floor(new_d + 1e-15))
            frac[i] = new_d - float(completed[i])
            want_pass[i] = -1
            st = _push(n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, t, L_OVERTAKE, i, ahead, 0, gap, OVERTAKE_ORDER_SNAP_LAPS)
            if st != ST_OK:
                return st
    return ST_OK


@njit(**_NJIT)
def exit_from_cfg(flag):
    return flag


@njit(**_NJIT)
def _advance_pit(i, t, completed, frac, phase, compound, tyre_age, pending_c, pending_s, pstart, pend, pclock, entry_completed, frozen, has_frozen, service_wait, team, nsets, mounted, inv_compound, inv_used, inv_age, used_extra, crew, n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, in_pit, box_frac, t_service, t_out, exit_f, stacking_forbidden, entry_frac):
    # exit_f is passed as the last real exit fraction; the dummy helper above is not used.
    ph = phase[i]
    if ph == PH_IN:
        entry_c = entry_completed[i]
        completed[i] = entry_c + 1
        frozen[i] = box_frac
        has_frozen[i] = 1
        frac[i] = box_frac
        pclock[i] = t
        arrival = t
        ti = team[i]
        crew_free = crew[ti]
        if stacking_forbidden == 1 and crew_free > arrival + EPS:
            return ST_STACK
        start = arrival if arrival > crew_free else crew_free
        wait = start - arrival
        service_wait[i] += wait
        crew[ti] = start + t_service
        box = _car_distance(i, in_pit, phase, completed, frac, entry_completed, entry_frac, frozen, has_frozen, pstart, pend, pclock)
        if wait > EPS:
            phase[i] = PH_WAIT
            pstart[i] = t
            pend[i] = start
            st = _push(n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, t, L_PIT_WAIT, i, 0, 0, wait, box)
            return st
        phase[i] = PH_SERVICE
        pstart[i] = t
        pend[i] = start + t_service
        st = _push(n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, t, L_SERVICE, i, 0, 0, 0.0, box)
        return st
    if ph == PH_WAIT:
        phase[i] = PH_SERVICE
        pstart[i] = t
        pend[i] = t + t_service
        frozen[i] = box_frac
        has_frozen[i] = 1
        box = _car_distance(i, in_pit, phase, completed, frac, entry_completed, entry_frac, frozen, has_frozen, pstart, pend, pclock)
        return _push(n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, t, L_SERVICE_AFTER, i, 0, 0, box, 0.0)
    if ph == PH_SERVICE:
        comp = pending_c[i]
        set_i = pending_s[i]
        if comp < 0 or set_i < 0:
            comp, set_i = _select_set(i, compound, inv_used, inv_compound, nsets, used_extra)
            if comp < 0:
                return ST_TYRE
        st = _mount(i, comp, set_i, compound, tyre_age, mounted, inv_compound, inv_used, inv_age, nsets, used_extra)
        if st != ST_OK:
            return st
        pending_c[i] = -1
        pending_s[i] = -1
        phase[i] = PH_OUT
        pstart[i] = t
        pend[i] = t + t_out
        frozen[i] = box_frac
        has_frozen[i] = 1
        return _push(n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, t, L_SERVICE_DONE, i, comp, set_i, float(entry_completed[i]), float(completed[i]))
    if ph == PH_OUT:
        in_pit[i] = 0
        phase[i] = PH_NONE
        pend[i] = np.nan
        pstart[i] = np.nan
        pclock[i] = np.nan
        frac[i] = exit_f
        frozen[i] = np.nan
        has_frozen[i] = 0
        progress = float(completed[i]) + frac[i]
        return _push(n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, t, L_PIT_EXIT, i, 0, 0, exit_f, progress)
    return ST_OK


@njit(**_NJIT)
def _overtakes(n, dt, completed, frac, in_pit, compound, tyre_age, fuel_a, retired, has_finish, speed, want_pass, car_rank, n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, t_box, regime, green, form_linear, wear, curv, offsets, time_scale, curve_scale, time_per_kg, adv_need, entry_completed, entry_frac, frozen, has_frozen, phase, pstart, pend, pclock):
    if regime != RG_GREEN or dt < 0.0:
        return ST_OK
    t = t_box[0]
    dist = np.empty(n, dtype=np.float64)
    order = np.empty(n, dtype=np.int64)
    for _pass in range(n):
        n_ord = 0
        for i in range(n):
            if in_pit[i] == 0 and has_finish[i] == 0 and retired[i] == 0:
                dist[i] = _car_distance(i, in_pit, phase, completed, frac, entry_completed, entry_frac, frozen, has_frozen, pstart, pend, pclock)
                order[n_ord] = i
                n_ord += 1
        _sort_order(order, n_ord, dist, car_rank)
        moved = 0
        for j in range(1, n_ord):
            i = order[j]
            ahead = order[j - 1]
            off_a = offsets[compound[ahead]]
            off_i = offsets[compound[i]]
            ft_a = _free_lap(green, off_a, tyre_age[ahead], form_linear, wear, curv, fuel_a[ahead], time_scale, curve_scale, time_per_kg)
            ft_i = _free_lap(green, off_i, tyre_age[i], form_linear, wear, curv, fuel_a[i], time_scale, curve_scale, time_per_kg)
            if ft_a - ft_i < adv_need - 1e-9:
                continue
            if speed[i] <= speed[ahead] + EPS:
                continue
            gap = dist[ahead] - dist[i]
            if gap > OVERTAKE_ORDER_SNAP_LAPS + EPS:
                continue
            new_d = dist[ahead] + OVERTAKE_ORDER_SNAP_LAPS
            completed[i] = int(math.floor(new_d + 1e-15))
            frac[i] = new_d - float(completed[i])
            want_pass[i] = -1
            st = _push(n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, t, L_OVERTAKE_TICK, i, ahead, 0, OVERTAKE_ORDER_SNAP_LAPS, 0.0)
            if st != ST_OK:
                return st
            moved = 1
            break
        if moved == 0:
            return ST_OK
    return ST_OK


@njit(**_NJIT)
def _maybe_finish(n, completed, frac, in_pit, phase, retired, has_finish, finish_time, entry_completed, entry_frac, frozen, has_frozen, pstart, pend, pclock, car_rank, n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, t_box, finished, leader_finished, leader_finish_t, leader_car, horizon):
    t = t_box[0]
    horizon_f = float(horizon)
    for i in range(n):
        if has_finish[i] == 0 and retired[i] == 1:
            finish_time[i] = t
            has_finish[i] = 1
        dist_i = _car_distance(i, in_pit, phase, completed, frac, entry_completed, entry_frac, frozen, has_frozen, pstart, pend, pclock)
        if has_finish[i] == 0 and retired[i] == 0 and dist_i + EPS >= horizon_f:
            completed[i] = horizon
            frac[i] = 0.0
            finish_time[i] = t
            has_finish[i] = 1
            st = _push(n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, t, L_FINISH, i, 0, 0, horizon_f, 0.0)
            if st != ST_OK:
                return st
    best = -1
    best_d = -1e300
    for i in range(n):
        dist_i = _car_distance(i, in_pit, phase, completed, frac, entry_completed, entry_frac, frozen, has_frozen, pstart, pend, pclock)
        better = dist_i > best_d or (dist_i == best_d and (best < 0 or car_rank[i] > car_rank[best]))
        if better:
            best = i
            best_d = dist_i
    leader_done = has_finish[best] == 1 or best_d + EPS >= horizon_f
    if not leader_done:
        return ST_OK
    if leader_finished[0] == 0:
        if has_finish[best] == 0:
            completed[best] = horizon
            frac[best] = 0.0
            finish_time[best] = t
            has_finish[best] = 1
        leader_finished[0] = 1
        leader_finish_t[0] = finish_time[best]
        leader_car[0] = best
        st = _push(n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1, t, L_LEADER, best, 0, 0, finish_time[best], 0.0)
        if st != ST_OK:
            return st
    finished[0] = 1
    return ST_OK


class KernelUnsupported(RuntimeError):
    def __init__(self, status: int):
        super().__init__(f"compiled continuation unsupported status={status}")
        self.status = int(status)


def _nan() -> float:
    return float("nan")


def pack_engine(engine) -> dict[str, Any]:
    """Copy scalar engine state into arrays. Does not mutate the engine."""
    state = engine.state
    cfg = engine.cfg
    cars = list(state["cars"].values())
    n = len(cars)
    if n > 32:
        raise KernelUnsupported(ST_UNSUPPORTED)
    ids = [car["car_id"] for car in cars]
    labels = ids + ["race"]
    rank_of = {name: i for i, name in enumerate(sorted(labels))}
    teams = []
    for car in cars:
        if car["team_id"] not in teams:
            teams.append(car["team_id"])
    max_sets = 1
    for car in cars:
        max_sets = max(max_sets, len(car["inventory"]))
    if max_sets > 12:
        raise KernelUnsupported(ST_UNSUPPORTED)
    completed = np.zeros(n, dtype=np.int64)
    frac = np.zeros(n, dtype=np.float64)
    in_pit = np.zeros(n, dtype=np.int64)
    phase = np.zeros(n, dtype=np.int64)
    compound = np.zeros(n, dtype=np.int64)
    tyre_age = np.zeros(n, dtype=np.float64)
    fuel_a = np.zeros(n, dtype=np.float64)
    fuel_e = np.zeros(n, dtype=np.float64)
    pit_this = np.zeros(n, dtype=np.int64)
    retired = np.zeros(n, dtype=np.int64)
    has_finish = np.zeros(n, dtype=np.int64)
    finish_time = np.zeros(n, dtype=np.float64)
    speed = np.zeros(n, dtype=np.float64)
    want_pass = np.full(n, -1, dtype=np.int64)
    pending_c = np.full(n, -1, dtype=np.int64)
    pending_s = np.full(n, -1, dtype=np.int64)
    pstart = np.full(n, np.nan, dtype=np.float64)
    pend = np.full(n, np.nan, dtype=np.float64)
    pclock = np.full(n, np.nan, dtype=np.float64)
    entry_completed = np.zeros(n, dtype=np.int64)
    entry_frac = np.zeros(n, dtype=np.float64)
    frozen = np.full(n, np.nan, dtype=np.float64)
    has_frozen = np.zeros(n, dtype=np.int64)
    service_wait = np.zeros(n, dtype=np.float64)
    team = np.zeros(n, dtype=np.int64)
    nsets = np.zeros(n, dtype=np.int64)
    mounted = np.zeros(n, dtype=np.int64)
    inv_compound = np.zeros((n, max_sets), dtype=np.int64)
    inv_used = np.zeros((n, max_sets), dtype=np.int64)
    inv_age = np.zeros((n, max_sets), dtype=np.float64)
    used_extra = np.zeros(n, dtype=np.int64)
    policy_kind = np.ones(n, dtype=np.int64)
    policy_delay = np.zeros(n, dtype=np.int64)
    policy_ref = np.full(n, -1, dtype=np.int64)
    policy_c = np.full(n, -1, dtype=np.int64)
    policy_s = np.full(n, -1, dtype=np.int64)
    car_rank = np.zeros(n, dtype=np.int64)
    set_ids: list[list[str]] = []
    phase_of = {None: PH_NONE, "transit_in": PH_IN, "waiting": PH_WAIT, "service": PH_SERVICE, "transit_out": PH_OUT}
    for i, car in enumerate(cars):
        completed[i] = int(car["completed_laps"])
        frac[i] = float(car["frac"])
        in_pit[i] = 1 if car["in_pit"] else 0
        phase[i] = phase_of[car.get("pit_phase")]
        if car["compound"] not in _COMPOUND:
            raise KernelUnsupported(ST_UNSUPPORTED)
        compound[i] = _COMPOUND[car["compound"]]
        tyre_age[i] = float(car["tyre_age_laps"])
        fuel_a[i] = float(car["fuel_actual"])
        fuel_e[i] = float(car["fuel_estimated"])
        pit_this[i] = 1 if car.get("pit_this_lap") else 0
        retired[i] = 1 if car.get("retired") else 0
        if car.get("finish_time") is not None:
            has_finish[i] = 1
            finish_time[i] = float(car["finish_time"])
        speed[i] = float(car.get("speed") or 0.0)
        if car.get("want_pass"):
            want_pass[i] = ids.index(car["want_pass"])
        sets = []
        for s, item in enumerate(car["inventory"]):
            inv_compound[i, s] = _COMPOUND[item["compound"]]
            inv_used[i, s] = 1 if item.get("used") else 0
            inv_age[i, s] = float(item.get("age_laps") or 0.0)
            sets.append(item["set_id"])
            if item["set_id"] == car["mounted_set_id"]:
                mounted[i] = s
        nsets[i] = len(sets)
        set_ids.append(sets)
        if car.get("pending_compound"):
            pending_c[i] = _COMPOUND[car["pending_compound"]]
        if car.get("pending_set_id"):
            pending_s[i] = sets.index(car["pending_set_id"])
        for name in ("pit_phase_start_t", "pit_phase_end", "pit_clock_t"):
            pass
        if car.get("pit_phase_start_t") is not None:
            pstart[i] = float(car["pit_phase_start_t"])
        if car.get("pit_phase_end") is not None:
            pend[i] = float(car["pit_phase_end"])
        if car.get("pit_clock_t") is not None:
            pclock[i] = float(car["pit_clock_t"])
        if car.get("pit_entry_completed_laps") is not None:
            entry_completed[i] = int(car["pit_entry_completed_laps"])
        if car.get("pit_entry_frac") is not None:
            entry_frac[i] = float(car["pit_entry_frac"])
        if car.get("frozen_frac") is not None:
            frozen[i] = float(car["frozen_frac"])
            has_frozen[i] = 1
        service_wait[i] = float(car.get("service_wait_s") or 0.0)
        team[i] = teams.index(car["team_id"])
        for comp_name in car.get("used_compounds") or []:
            used_extra[i] |= 1 << _COMPOUND[comp_name]
        car_rank[i] = rank_of[car["car_id"]]
        pol = state["policies"].get(car["car_id"]) or {"kind": "continuation"}
        kind = pol.get("kind")
        if kind in {None, "continuation"}:
            policy_kind[i] = PK_CONT
        elif kind == "pit_now":
            policy_kind[i] = PK_PIT
        elif kind == "delay_laps":
            policy_kind[i] = PK_DELAY
            policy_delay[i] = int(pol.get("delay_laps") or 0)
            if pol.get("reference_completed") is not None:
                policy_ref[i] = int(pol["reference_completed"])
        else:
            raise KernelUnsupported(ST_UNSUPPORTED)
        if pol.get("compound"):
            policy_c[i] = _COMPOUND[pol["compound"]]
        if pol.get("set_id"):
            policy_s[i] = sets.index(pol["set_id"])
    crew = np.full(len(teams), -BIG, dtype=np.float64)
    for name, value in state["crew_free_at"].items():
        crew[teams.index(name)] = float(value)
    reg = {"GREEN": RG_GREEN, "SC": RG_SC, "VSC": RG_VSC}[state["regime"]]
    prio = {name: i for i, name in enumerate(cfg["integrator"]["simultaneous_priority"])}
    parts = state["pit_parts"]
    offsets = [float(cfg["tyres"]["compound_offset_s"][name]) for name in _COMPOUND_NAME]
    cap = 200_000
    return {
        "ids": ids,
        "teams": teams,
        "set_ids": set_ids,
        "n": n,
        "max_sets": max_sets,
        "arrays": (
            completed, frac, in_pit, phase, compound, tyre_age, fuel_a, fuel_e, pit_this, retired,
            has_finish, finish_time, speed, want_pass, pending_c, pending_s, pstart, pend, pclock,
            entry_completed, entry_frac, frozen, has_frozen, service_wait, team, nsets, mounted,
            inv_compound, inv_used, inv_age, used_extra, policy_kind, policy_delay, policy_ref,
            policy_c, policy_s, car_rank, crew,
        ),
        "events": (
            np.zeros(1, dtype=np.int64),
            np.zeros(cap, dtype=np.float64),
            np.zeros(cap, dtype=np.int64),
            np.zeros(cap, dtype=np.int64),
            np.zeros(cap, dtype=np.int64),
            np.zeros(cap, dtype=np.int64),
            np.zeros(cap, dtype=np.float64),
            np.zeros(cap, dtype=np.float64),
        ),
        "scalars": {
            "t": np.array([float(state["t"])], dtype=np.float64),
            "finished": np.array([1 if state.get("finished") else 0], dtype=np.int64),
            "regime": np.array([reg], dtype=np.int64),
            "regime_end": np.array([float(state["regime_end_s"]) if state.get("regime_end_s") is not None else np.nan], dtype=np.float64),
            "has_regime_end": np.array([0 if state.get("regime_end_s") is None else 1], dtype=np.int64),
            "leader_finished": np.array([1 if state.get("leader_finished") else 0], dtype=np.int64),
            "leader_finish_t": np.array([float(state.get("leader_finish_t") or 0.0)], dtype=np.float64),
            "leader_car": np.array([-1], dtype=np.int64),
            "horizon": int(state["horizon"]),
            "required": int(state["required_compounds"]),
            "green": float(state["green_lap_s"]),
            "form_linear": 1 if state["tyre_form"] == "near_linear" else 0,
            "wear": float(state["tyre_wear"]),
            "curv": float(state.get("tyre_curvature") or 0.0),
            "offsets": offsets,
            "time_scale": float(cfg["tyres"]["time_scale_s"]),
            "curve_scale": float(cfg["tyres"]["curve_scale_s"]),
            "time_per_kg": float(cfg["fuel"]["time_per_kg_s"]),
            "kg_per_lap": float(cfg["fuel"]["kg_per_lap"]),
            "min_gap_s": float(cfg["traffic"]["min_gap_s"]),
            "attack_s": float(cfg["traffic"]["attack_range_s"]),
            "adv_need": float(cfg["traffic"]["overtake_advantage_s_per_lap"]),
            "sc_factor": float(cfg["regime"]["sc_pace_factor"]),
            "vsc_factor": float(cfg["regime"]["vsc_pace_factor"]),
            "sc_catch": float(cfg["regime"]["sc_catch_factor"]),
            "sc_queue_gap": float(cfg["regime"]["sc_queue_gap_s"]),
            "dt_green": float(cfg["integrator"]["dt_max_green_s"]),
            "dt_regime": float(cfg["integrator"]["dt_max_regime_s"]),
            "entry": float(cfg["track"]["pit_entry_frac"]),
            "exit_f": float(cfg["track"]["pit_exit_frac"]),
            "box_frac": float(cfg["track"].get("pit_box_frac", 0.0)),
            "t_in": float(parts["t_in_s"]),
            "t_service": float(parts["t_service_s"]),
            "t_out": float(parts["t_out_s"]),
            "stacking_forbidden": 1 if state.get("stacking_policy") == "forbidden" else 0,
            "prio_catch": int(prio.get("catch_or_pass", 50)),
            "prio_lap": int(prio.get("lap_complete", 50)),
            "prio_pit_entry": int(prio.get("pit_entry", 50)),
            "prio_pit_timer": int(prio.get("pit_timer", 50)),
            "prio_regime": int(prio.get("regime_end", 50)),
            "prio_sc": int(prio.get("sc_gap_meet", 50)),
            "race_rank": int(rank_of["race"]),
            "checkpoint_reached": bool(state.get("checkpoint_reached")),
        },
    }


def _materialize(packed, n_new: int) -> list[dict[str, Any]]:
    n_ev, ev_t, ev_k, ev_c, ev_i0, ev_i1, ev_f0, ev_f1 = packed["events"]
    ids = packed["ids"]
    set_ids = packed["set_ids"]
    out = []
    note_leader = "Race end is leader-triggered; other cars keep individual finish_time only if they crossed"
    note_service = "service_complete is not the pit-entry lap; use pit_entry event / pit_entry_completed_laps"
    for i in range(n_new):
        k = int(ev_k[i])
        c = int(ev_c[i])
        car = None if c < 0 else ids[c]
        if k == L_LAP:
            detail = {"completed_laps": int(ev_i0[i])}
            kind = "lap_complete"
        elif k == L_LAP_SNAP:
            detail = {"completed_laps": int(ev_i0[i]), "snapped": True}
            kind = "lap_complete"
        elif k == L_FINISH:
            detail = {"progress": float(ev_f0[i]), "individual": True}
            kind = "car_finish"
        elif k == L_REGIME:
            detail = {"restart": "instantaneous_green_pace_preserve_gaps"}
            kind = "regime_end"
        elif k == L_SC:
            detail = {"ahead": ids[int(ev_i0[i])]}
            kind = "sc_gap_meet"
        elif k == L_PIT_ENTRY:
            detail = {"t_in_s": float(ev_f0[i]), "pit_entry_completed_laps": int(ev_i0[i]), "completed_laps": int(ev_i1[i])}
            kind = "pit_entry"
        elif k == L_PIT_WAIT:
            detail = {"wait_s": float(ev_f0[i]), "box_progress": float(ev_f1[i])}
            kind = "pit_wait"
        elif k == L_SERVICE:
            detail = {"wait_s": float(ev_f0[i]), "box_progress": float(ev_f1[i])}
            kind = "service_start"
        elif k == L_SERVICE_AFTER:
            detail = {"after_wait": True, "box_progress": float(ev_f0[i])}
            kind = "service_start"
        elif k == L_SERVICE_DONE:
            detail = {
                "compound": _COMPOUND_NAME[int(ev_i0[i])],
                "set_id": set_ids[c][int(ev_i1[i])],
                "pit_entry_completed_laps": int(ev_f0[i]),
                "completed_laps_at_service": int(ev_f1[i]),
                "note": note_service,
            }
            kind = "service_complete"
        elif k == L_PIT_EXIT:
            detail = {"frac": float(ev_f0[i]), "progress": float(ev_f1[i])}
            kind = "pit_exit"
        elif k == L_OVERTAKE:
            detail = {
                "passed": ids[int(ev_i0[i])],
                "order_snap_laps": float(ev_f1[i]),
                "pre_pass_gap_laps": float(ev_f0[i]),
                "not_pass_clearance_teleport": True,
                "fuel_tyre_time_unchanged": True,
            }
            kind = "overtake"
        elif k == L_OVERTAKE_TICK:
            detail = {
                "passed": ids[int(ev_i0[i])],
                "resolver": "tick_resolution",
                "order_snap_laps": float(ev_f0[i]),
                "not_pass_clearance_teleport": True,
            }
            kind = "overtake"
        elif k == L_LEADER:
            detail = {"t": float(ev_f0[i]), "note": note_leader}
            kind = "leader_finish"
        elif k == L_EXPIRED:
            detail = {"frac": float(ev_f0[i]), "not_relabelled_next_lap": True}
            kind = "pit_now_expired"
        else:
            raise KernelUnsupported(ST_UNSUPPORTED)
        out.append({"t": round(float(ev_t[i]), 9), "kind": kind, "car_id": car, "detail": detail})
    return out


def compiled_continue(engine, *, max_steps: int = 2_000_000) -> int:
    """Advance a scalar engine with the compiled loop. Writes back only on success."""
    state = engine.state
    if not state.get("checkpoint_reached"):
        raise KernelUnsupported(ST_UNSUPPORTED)
    if state.get("finished"):
        return ST_OK
    packed = pack_engine(engine)
    sc = packed["scalars"]
    arrays = packed["arrays"]
    ev = packed["events"]
    off = sc["offsets"]
    status = int(
        run_continuation(
            packed["n"],
            int(max_steps),
            int(packed["max_sets"]),
            *arrays,
            *ev,
            sc["t"],
            sc["finished"],
            sc["regime"],
            sc["regime_end"],
            sc["has_regime_end"],
            sc["leader_finished"],
            sc["leader_finish_t"],
            sc["leader_car"],
            int(sc["horizon"]),
            int(sc["required"]),
            float(sc["green"]),
            int(sc["form_linear"]),
            float(sc["wear"]),
            float(sc["curv"]),
            float(off[0]),
            float(off[1]),
            float(off[2]),
            float(sc["time_scale"]),
            float(sc["curve_scale"]),
            float(sc["time_per_kg"]),
            float(sc["kg_per_lap"]),
            float(sc["min_gap_s"]),
            float(sc["attack_s"]),
            float(sc["adv_need"]),
            float(sc["sc_factor"]),
            float(sc["vsc_factor"]),
            float(sc["sc_catch"]),
            float(sc["sc_queue_gap"]),
            float(sc["dt_green"]),
            float(sc["dt_regime"]),
            float(sc["entry"]),
            float(sc["exit_f"]),
            float(sc["box_frac"]),
            float(sc["t_in"]),
            float(sc["t_service"]),
            float(sc["t_out"]),
            int(sc["stacking_forbidden"]),
            int(sc["prio_catch"]),
            int(sc["prio_lap"]),
            int(sc["prio_pit_entry"]),
            int(sc["prio_pit_timer"]),
            int(sc["prio_regime"]),
            int(sc["prio_sc"]),
            int(sc["race_rank"]),
        )
    )
    if status != ST_OK:
        raise KernelUnsupported(status)
    _writeback(engine, packed)
    return status


def _writeback(engine, packed) -> None:
    state = engine.state
    (
        completed, frac, in_pit, phase, compound, tyre_age, fuel_a, fuel_e, pit_this, retired,
        has_finish, finish_time, speed, want_pass, pending_c, pending_s, pstart, pend, pclock,
        entry_completed, entry_frac, frozen, has_frozen, service_wait, team, nsets, mounted,
        inv_compound, inv_used, inv_age, used_extra, policy_kind, policy_delay, policy_ref,
        policy_c, policy_s, car_rank, crew,
    ) = packed["arrays"]
    ids = packed["ids"]
    phase_name = {PH_NONE: None, PH_IN: "transit_in", PH_WAIT: "waiting", PH_SERVICE: "service", PH_OUT: "transit_out"}
    kind_name = {PK_CONT: "continuation", PK_PIT: "pit_now", PK_DELAY: "delay_laps"}
    cars = state["cars"]
    for i, cid in enumerate(ids):
        car = cars[cid]
        car["completed_laps"] = int(completed[i])
        car["frac"] = float(frac[i])
        car["in_pit"] = bool(in_pit[i])
        car["pit_phase"] = phase_name[int(phase[i])]
        car["compound"] = _COMPOUND_NAME[int(compound[i])]
        car["tyre_age_laps"] = float(tyre_age[i])
        car["fuel_actual"] = float(fuel_a[i])
        car["fuel_estimated"] = float(fuel_e[i])
        car["pit_this_lap"] = bool(pit_this[i])
        car["retired"] = bool(retired[i])
        car["finish_time"] = float(finish_time[i]) if has_finish[i] else None
        car["speed"] = float(speed[i])
        car["want_pass"] = None if want_pass[i] < 0 else ids[int(want_pass[i])]
        car["pending_compound"] = None if pending_c[i] < 0 else _COMPOUND_NAME[int(pending_c[i])]
        car["pending_set_id"] = None if pending_s[i] < 0 else packed["set_ids"][i][int(pending_s[i])]
        car["pit_phase_start_t"] = None if math.isnan(pstart[i]) else float(pstart[i])
        car["pit_phase_end"] = None if math.isnan(pend[i]) else float(pend[i])
        car["pit_clock_t"] = None if math.isnan(pclock[i]) else float(pclock[i])
        car["pit_entry_completed_laps"] = int(entry_completed[i]) if in_pit[i] or has_frozen[i] or int(phase[i]) != PH_NONE else car.get("pit_entry_completed_laps")
        car["pit_entry_frac"] = float(entry_frac[i]) if in_pit[i] else car.get("pit_entry_frac")
        car["frozen_frac"] = None if has_frozen[i] == 0 or math.isnan(frozen[i]) else float(frozen[i])
        car["service_wait_s"] = float(service_wait[i])
        car["mounted_set_id"] = packed["set_ids"][i][int(mounted[i])]
        for s in range(int(nsets[i])):
            item = car["inventory"][s]
            item["used"] = bool(inv_used[i, s])
            item["age_laps"] = float(inv_age[i, s])
            item["compound"] = _COMPOUND_NAME[int(inv_compound[i, s])]
        used = []
        for bit, name in enumerate(_COMPOUND_NAME):
            if used_extra[i] & (1 << bit):
                used.append(name)
        if car["compound"] not in used:
            used.append(car["compound"])
        car["used_compounds"] = used
        pol = state["policies"].get(cid) or {}
        pol = dict(pol)
        pol["kind"] = kind_name[int(policy_kind[i])]
        if policy_kind[i] == PK_DELAY:
            pol["delay_laps"] = int(policy_delay[i])
            if policy_ref[i] >= 0:
                pol["reference_completed"] = int(policy_ref[i])
        state["policies"][cid] = pol
    sc = packed["scalars"]
    state["t"] = float(sc["t"][0])
    state["finished"] = bool(sc["finished"][0])
    state["regime"] = {RG_GREEN: "GREEN", RG_SC: "SC", RG_VSC: "VSC"}[int(sc["regime"][0])]
    state["regime_end_s"] = None if sc["has_regime_end"][0] == 0 or math.isnan(sc["regime_end"][0]) else float(sc["regime_end"][0])
    state["leader_finished"] = bool(sc["leader_finished"][0])
    if sc["leader_finished"][0]:
        state["leader_finish_t"] = float(sc["leader_finish_t"][0])
        if int(sc["leader_car"][0]) >= 0:
            state["leader_finish_car_id"] = ids[int(sc["leader_car"][0])]
    state["finish_t"] = state["t"]
    for name, idx in ((name, i) for i, name in enumerate(packed["teams"])):
        state["crew_free_at"][name] = float(crew[idx])
    n_new = int(packed["events"][0][0])
    state["events"].extend(_materialize(packed, n_new))
    if state.get("leader_finished"):
        from f1q.simulator.classification import classify
        from f1q.simulator.engine import distance

        progress = {cid: distance(car) for cid, car in cars.items()}
        finish = {cid: car["finish_time"] for cid, car in cars.items()}
        state["rank_at_leader_finish"] = classify(progress, finish)


def candidate_finish(sim) -> dict[str, Any]:
    """Finish one committed simulator. Raises if the kernel cannot cover the state."""
    compiled_continue(sim.engine)
    return sim.engine.outcome()


def candidate_cache_key(**kwargs: Any) -> str:
    """Cache identity that changes when the compiled kernel version changes."""
    from f1q.a4.banks import cache_key
    from f1q.hashing import sha256_json

    base = cache_key(**kwargs)
    return sha256_json({"continuation_key": base, "backend": "candidate", "kernel_version": KERNEL_VERSION})
