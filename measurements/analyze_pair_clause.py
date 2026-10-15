#!/usr/bin/env python3
"""Per-event pair-difference timing clause at the family-wise threshold.

This script computes the quantity that lem:coincidence-timing (EXTp, App A)
and CST_Model.thy actually define:

    timing clause fires on (T_o, T_c)  :<=>  exists i. |T_c[i] - T_o[i]| > Dstar
    Dstar = k_n * sigma,  sigma = sample stdev (n-1) of T_o (post-warm-up),
    k_n   = sqrt(2) * z_{1 - alpha/(2n)}   (family-wise over the n events,
            nominal alpha = 0.05; the sqrt(2) is the difference of two samples)

and reports, from EXTp's own boot logs:
  (1) NULL  — zero-intervention pairs: both halves of one boot's cond=0
      samples (interleaved split).  Per-event exceedance and family-wise
      fire rate with a Clopper-Pearson 95% upper bound, at k = 1.645 (the
      previous per-event threshold) and at k_n.
  (2) SWEEP — cond 0 vs cond c of the same boot, aligned by position:
      does the clause fire at k_n, and how many events exceed.

It replaces the per-sample one-sided test (x_i > mean + 1.645 sigma) of
analyze_l2_sweep.py as the source of the FPR quoted in the lemma.
Pure stdlib; run:  python3 analyze_pair_clause.py boot_log*.txt
"""
import re, sys, statistics
from collections import defaultdict
from statistics import NormalDist

WARMUP = 20          # EXTP_INNER_WARMUP_SAMPLES
ALPHA  = 0.05
RAW_C = re.compile(r'\[EXTp\]\[TIMING_RAW\] sample=(\d+) cond=(\d+) nopcount=(\d+) delta=(\d+)')
RAW_N = re.compile(r'\[EXTp\]\[TIMING_RAW\] sample=(\d+) delta=(\d+)')
BOOT  = re.compile(r'\[EXTp\]\[BOOT\] boot_count=|BOOT_START boot=')

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from kn_table import k_float as k_n   # table value floor(k_n*2^16)/2^16 -- the definition (v2.1)

def _bcdf(x, n, p):
    from math import lgamma, log, exp
    if p <= 0: return 1.0
    if p >= 1: return 0.0 if x < n else 1.0
    return sum(exp(lgamma(n+1) - lgamma(i+1) - lgamma(n-i+1) + i*log(p) + (n-i)*log(1-p)) for i in range(x + 1))

def cp_upper(x, n, conf=0.95):
    """Clopper-Pearson one-sided upper bound (bisection on the binomial cdf)."""
    if x >= n: return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if _bcdf(x, n, mid) > 1 - conf: lo = mid
        else: hi = mid
    return hi

def cp_ci(x, n, conf=0.95):
    """Clopper-Pearson two-sided interval."""
    if x == 0: lo = 0.0
    else:
        a, b = 0.0, 1.0
        for _ in range(60):
            mid = (a + b) / 2
            if 1 - _bcdf(x - 1, n, mid) < (1 - conf) / 2: a = mid
            else: b = mid
        lo = a
    return lo, cp_upper(x, n, 1 - (1 - conf) / 2)

def parse(path):
    boots, cur = [], None
    with open(path, errors='replace') as f:
        for line in f:
            if BOOT.search(line):
                if cur: boots.append(cur)
                cur = defaultdict(list); continue
            m = RAW_C.search(line)
            if m: idx, cond, nop, d = (int(g) for g in m.groups())
            else:
                m = RAW_N.search(line)
                if not m: continue
                idx, d, cond, nop = int(m[1]), int(m[2]), 0, 0
            if cur is None: cur = defaultdict(list)
            cur[cond].append((idx, nop, d))
    if cur: boots.append(cur)
    return [b for b in boots if b]

def clause(To, Tc, k):
    n = min(len(To), len(Tc)); To, Tc = To[:n], Tc[:n]
    s = statistics.stdev(To); ds = k * s
    ex = sum(1 for a, b in zip(To, Tc) if abs(b - a) > ds)
    return ex, n, s

def main():
    null = {'1.645': [0, 0, 0, 0], 'k_n': [0, 0, 0, 0]}   # fires, pairs, exceed events, events
    print("=== (1) NULL: zero-intervention pairs (interleaved halves of cond=0, same boot) ===")
    print(f"{'boot':34s} {'n':>4s} {'k_n':>5s} {'sigma':>7s} | exceed@1.645  fire | exceed@k_n  fire")
    sweep = []
    for path in sys.argv[1:]:
        name = path.split('/')[-1]
        for bi, b in enumerate(parse(path)):
            post = {c: [d for i, nop, d in xs if i >= WARMUP] for c, xs in b.items()}
            nop  = {c: (xs[0][1] if xs else 0) for c, xs in b.items()}
            T0 = post.get(0, [])
            if len(T0) < 8: continue
            A, B = T0[0::2], T0[1::2]; h = min(len(A), len(B)); kn = k_n(h)
            row = []
            for key, k in (('1.645', 1.645), ('k_n', kn)):
                ex, n, s = clause(A, B, k)
                null[key][0] += (ex > 0); null[key][1] += 1; null[key][2] += ex; null[key][3] += n
                row.append((ex, n, s, ex > 0))
            print(f"{name+'#b'+str(bi):34s} {h:4d} {kn:5.2f} {row[0][2]:7.0f} | {row[0][0]:3d}/{row[0][1]:<3d} {str(row[0][3]):>7s} | {row[1][0]:3d}/{row[1][1]:<3d} {str(row[1][3]):>6s}")
            for c in sorted(post):
                if c == 0 or len(post[c]) < 8: continue
                n = min(len(T0), len(post[c])); k2 = k_n(n)
                ex, _, s = clause(T0, post[c], k2)
                shift = statistics.fmean(post[c][:n]) - statistics.fmean(T0[:n])
                sweep.append((f"{name}#b{bi} cond={c} iter={nop[c]}", n, k2, s, shift, ex))
    print("\n=== (1) summary ===")
    for key, (f, p, ex, ev) in null.items():
        fl, fu = cp_ci(f, p); el, eu = cp_ci(ex, ev)
        print(f"  k={key:5s}: family-wise fire {f}/{p} = {100*f/p:5.1f}%  (CP 95% CI [{100*fl:.1f}%, {100*fu:.1f}%], one-sided upper {100*cp_upper(f, p):.1f}%)"
              f"\n           per-event exceedance {ex}/{ev} = {100*ex/ev:5.2f}%  (CP 95% CI [{100*el:.2f}%, {100*eu:.2f}%], one-sided upper {100*cp_upper(ex, ev):.2f}%)")
    print(f"  nominal family-wise alpha = {100*ALPHA:.0f}%")
    print("\n=== (2) SWEEP: cond 0 vs cond c (same boot, aligned), clause at k_n ===")
    print(f"{'pair':38s} {'n':>4s} {'k_n':>5s} {'sigma':>7s} {'mean shift':>11s} {'shift/sig':>9s}  exceed  fire")
    for tag, n, k2, s, shift, ex in sweep:
        print(f"{tag:38s} {n:4d} {k2:5.2f} {s:7.0f} {shift:11.0f} {shift/s:9.2f}  {ex:3d}/{n:<3d}  {ex > 0}")

if __name__ == '__main__':
    main()
