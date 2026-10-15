#!/usr/bin/env python3
"""Tail check (review round 10): do the events that exceed k_n*sigma in
zero-intervention pairs coincide with a recorded noise marker?

Markers available in TIMING_RAW lines (no SMI counter is logged):
  pstate  : perf_status_s != perf_status_e   (P-state transition inside the sample)
  therm   : therm_s != therm_e               (thermal status change inside the sample)
  freq    : aperf_d/mperf_d ratio of the event deviates from the boot median by > 2%
  mperf   : mperf_d of the event deviates from the boot median by > 2% (reference-cycle
            count of the window — a long interruption inflates it)
For every exceeding event (in either half of the pair) we print the markers
of the two samples involved, and summarise marker rates on exceeding vs.
non-exceeding events.
"""
import re, sys, statistics
from collections import defaultdict
from statistics import NormalDist

WARMUP, ALPHA = 20, 0.05
RAW = re.compile(r'\[EXTp\]\[TIMING_RAW\] sample=(\d+) cond=(\d+) nopcount=\d+ delta=(\d+) '
                 r'mperf_d=(\d+) aperf_d=(\d+) perf_status_s=(\S+) perf_status_e=(\S+) therm_s=(\S+) therm_e=(\S+)')
BOOT = re.compile(r'\[EXTp\]\[BOOT\] boot_count=|BOOT_START boot=')

def k_n(n): return 2 ** 0.5 * NormalDist().inv_cdf(1 - ALPHA / (2 * n))

def parse(path):
    boots, cur = [], None
    with open(path, errors='replace') as f:
        for line in f:
            if BOOT.search(line):
                if cur: boots.append(cur)
                cur = defaultdict(list); continue
            m = RAW.search(line)
            if not m: continue
            if cur is None: cur = defaultdict(list)
            idx, cond, d, mp, ap = (int(m[i]) for i in range(1, 6))
            cur[cond].append(dict(idx=idx, d=d, mp=mp, ap=ap, ps=(m[6] != m[7]), th=(m[8] != m[9])))
    if cur: boots.append(cur)
    return [b for b in boots if b]

def main():
    tot = {'exceed': defaultdict(int), 'other': defaultdict(int)}; nev = {'exceed': 0, 'other': 0}
    print(f"{'boot':30s} {'i':>4s} {'|diff|/sig':>9s}  sample-A markers / sample-B markers   (raw deltas)")
    for path in sys.argv[1:]:
        name = path.split('/')[-1]
        for bi, b in enumerate(parse(path)):
            T0 = [e for e in b.get(0, []) if e['idx'] >= WARMUP]
            if len(T0) < 8: continue
            A, B = T0[0::2], T0[1::2]; n = min(len(A), len(B)); A, B = A[:n], B[:n]
            s = statistics.stdev(e['d'] for e in A); k = k_n(n)
            mpm = statistics.median(e['mp'] for e in T0); rtm = statistics.median(e['ap'] / e['mp'] for e in T0 if e['mp'])
            def marks(e):
                m = []
                if e['ps']: m.append('pstate')
                if e['th']: m.append('therm')
                if e['mp'] and abs(e['ap'] / e['mp'] - rtm) / rtm > 0.02: m.append('freq')
                if abs(e['mp'] - mpm) / mpm > 0.02: m.append('mperf')
                return m
            for i, (a, c) in enumerate(zip(A, B)):
                z = abs(c['d'] - a['d']) / s
                cls = 'exceed' if z > k else 'other'
                ma, mc = marks(a), marks(c); nev[cls] += 1
                for m in set(ma) | set(mc): tot[cls][m] += 1
                if not (ma or mc): tot[cls]['none'] += 1
                if cls == 'exceed':
                    print(f"{name+'#b'+str(bi):30s} {i:4d} {z:9.2f}  {','.join(ma) or '-':>22s} / {','.join(mc) or '-':<22s} ({a['d']}, {c['d']})")
    print("\n=== marker rate on exceeding vs non-exceeding events ===")
    for cls in ('exceed', 'other'):
        n = nev[cls] or 1
        print(f"  {cls:7s} events={nev[cls]:6d}  " + "  ".join(f"{m}={100*tot[cls][m]/n:5.1f}%" for m in ('pstate', 'therm', 'freq', 'mperf', 'none')))

if __name__ == '__main__':
    main()
