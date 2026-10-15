#!/usr/bin/env python3
"""gen_numbers.py -- derive every measured number the paper quotes from the raw
logs and emit them as LaTeX macros, so the text cannot drift from the data.

    python3 gen_numbers.py --logs DIR [--out extp_numbers.tex] [--set paper|all]

Inputs (all in DIR, as shipped in the artifact's logs/ directory):
  boot_log*.txt                     per-event timing samples (TIMING_RAW); the
                                    null (zero-intervention) pairs of sec:mi and
                                    the calibration sweeps of boot_log12/15
  CST_Demonstration5.txt            silent-hook demonstration (sec:eval-demo)
  CST_Demonstration3.txt            naive-hook counter-demonstration
  CST_Demonstration4.txt            cross-boot probe of the synthetic guest (3 boots in alternation)

Pure stdlib.  Every quantity is computed the way the paper defines it:
  sigma_base  sample standard deviation (n-1) of the post-warm-up (idx >= 20)
              zero-perturbation samples of one boot
  k_n         sqrt(2) * z_{1 - alpha/(2n)},  alpha = 0.05
  Dstar       k_n * sigma_base
  clause      exists i. |T_c[i] - T_o[i]| > Dstar   (pair-difference, per event)
  null pairs  interleaved halves of one boot's cond=0 samples
  CIs         Clopper-Pearson (binomial), chi^2 (sigma), 95 %
The two inputs that come from other measurements (eps_SOE bounds) are
constants below, marked as such.
"""
import argparse, math, re, statistics, sys
from collections import defaultdict
from statistics import NormalDist

WARMUP = 20            # EXTP_INNER_WARMUP_SAMPLES
ALPHA = 0.05
K_OLD = 1.645          # version-1 per-event threshold multiplier (erratum)
# From sec:capsep (not recomputed here): one-sided 95 % Clopper-Pearson upper
# bounds on the SOE-clause failure rate, in percent.
EPS_WITHIN_PCT = 0.37  # N = 998 within-boot
EPS_CROSS_PCT = 10.4   # N = 34 cross-boot
GHZ = 4.9

RAW_C = re.compile(r'\[EXTp\]\[TIMING_RAW\] sample=(\d+) cond=(\d+) nopcount=(\d+) delta=(\d+)')
RAW_N = re.compile(r'\[EXTp\]\[TIMING_RAW\] sample=(\d+) delta=(\d+)')
BOOT = re.compile(r'\[EXTp\]\[BOOT\] boot_count=|BOOT_START boot=')
import glob, os
# The paper's zero-intervention set (sec:mi, lem:coincidence-timing): the two
# cross-boot campaigns reported in the paper (N=34 archive; the N=100 campaign,
# 29 boots collected) plus the marker-instrumented calibration/sweep/demo logs
# boot_log8-16.  boot_log.txt .. boot_log7.txt are first-day development runs
# (overlapping partial captures of an N=20 campaign, a CMOS-only test, the first
# single-boot instrument test); they ship in logs/ and `--set all` includes them.
PAPER_SET = [f'boot_log{i}.txt' for i in range(8, 17)] + ['boot_logN34_archive.txt', 'boot_logN100_final.txt']
def null_logs(d, which):
    if which == 'paper': return PAPER_SET
    return sorted(os.path.basename(x) for x in glob.glob(os.path.join(d, 'boot_log*.txt')))


def k_n(n, alpha=ALPHA):
    return 2 ** 0.5 * NormalDist().inv_cdf(1 - alpha / (2 * n))


# ---------- binomial / Clopper-Pearson ----------
def _bcdf(x, n, p):
    if p <= 0: return 1.0
    if p >= 1: return 0.0 if x < n else 1.0
    lg = math.lgamma
    return sum(math.exp(lg(n + 1) - lg(i + 1) - lg(n - i + 1) + i * math.log(p) + (n - i) * math.log(1 - p))
               for i in range(x + 1))

def cp_upper(x, n, conf):
    if x >= n: return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if _bcdf(x, n, mid) > 1 - conf: lo = mid
        else: hi = mid
    return hi

def cp_ci(x, n, conf=0.95):
    if x == 0: lo = 0.0
    else:
        a, b = 0.0, 1.0
        for _ in range(60):
            mid = (a + b) / 2
            if 1 - _bcdf(x - 1, n, mid) < (1 - conf) / 2: a = mid
            else: b = mid
        lo = a
    return lo, cp_upper(x, n, 1 - (1 - conf) / 2)


# ---------- chi-square quantile (regularized lower incomplete gamma) ----------
def _gammainc(a, x):
    if x <= 0: return 0.0
    if x < a + 1:                       # series
        s = t = 1.0 / a
        for n in range(1, 500):
            t *= x / (a + n); s += t
            if abs(t) < abs(s) * 1e-15: break
        return s * math.exp(-x + a * math.log(x) - math.lgamma(a))
    # continued fraction (Lentz)
    b = x + 1 - a; c = 1e300; d = 1 / b; h = d
    for i in range(1, 500):
        an = -i * (i - a); b += 2
        d = an * d + b; d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c; c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d; delta = d * c; h *= delta
        if abs(delta - 1) < 1e-15: break
    return 1 - math.exp(-x + a * math.log(x) - math.lgamma(a)) * h

def chi2_ppf(q, df):
    lo, hi = 0.0, 50.0 * max(df, 1)
    for _ in range(200):
        mid = (lo + hi) / 2
        if _gammainc(df / 2, mid / 2) < q: lo = mid
        else: hi = mid
    return (lo + hi) / 2

def sigma_ci(sd, n, alpha=0.05):
    df = n - 1
    return sd * math.sqrt(df / chi2_ppf(1 - alpha / 2, df)), sd * math.sqrt(df / chi2_ppf(alpha / 2, df))


# ---------- parsing ----------
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

def post(b):
    return {c: [d for i, nop, d in xs if i >= WARMUP] for c, xs in b.items()}

def clause(To, Tc, k):
    n = min(len(To), len(Tc)); To, Tc = To[:n], Tc[:n]
    s = statistics.stdev(To)
    return sum(1 for a, b in zip(To, Tc) if abs(b - a) > k * s), n, s

def ols_slope(xs, ys):
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)


# ---------- formatting ----------
def grp(v):                       # 27323 -> 27{,}323 (LaTeX thousands)
    s = f'{int(round(v)):,}'
    return s.replace(',', '{,}')

def pct(v, d=2): return f'{v:.{d}f}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--logs', required=True)
    ap.add_argument('--out', default='extp_numbers.tex')
    ap.add_argument('--set', choices=['paper', 'all'], default='paper', help='zero-intervention log set (see PAPER_SET)')
    a = ap.parse_args()
    L = a.logs.rstrip('/') + '/'
    M = {}   # macro name -> value (string)

    # ===== (1) null pairs: realized FPR with the clause =====
    fam_kn = fam_old = pairs = ex_kn = ex_old = events = 0
    exp_nominal = 0.0
    per_log = {}
    names = null_logs(L, a.set); M['NullLogs'] = str(len(names))
    for name in names:
        for b in parse(L + name):
            T0 = post(b).get(0, [])
            if len(T0) < 8: continue
            A, B = T0[0::2], T0[1::2]; h = min(len(A), len(B))
            e_old, n, _ = clause(A, B, K_OLD)
            e_kn, n, _ = clause(A, B, k_n(h))
            pairs += 1; events += n
            fam_old += e_old > 0; fam_kn += e_kn > 0
            ex_old += e_old; ex_kn += e_kn
            exp_nominal += n * (ALPHA / h)     # Gaussian nominal per-event rate alpha/n, summed
            per_log.setdefault(name, [0, 0]); per_log[name][0] += e_kn; per_log[name][1] += n
    lo, hi = cp_ci(ex_kn, events); flo, fhi = cp_ci(fam_kn, pairs)
    nominal_pct = 100 * exp_nominal / events
    M['NullBoots'] = str(pairs); M['NullEvents'] = grp(events)
    M['NullExceedKn'] = str(ex_kn); M['FamFireKn'] = str(fam_kn)
    M['ARealized'] = pct(100 * ex_kn / events); M['ARealizedLo'] = pct(100 * lo); M['ARealizedHi'] = pct(100 * hi)
    M['FamRate'] = pct(100 * fam_kn / pairs, 1); M['FamLo'] = pct(100 * flo, 1); M['FamHi'] = pct(100 * fhi, 1)
    M['NominalEvent'] = pct(nominal_pct); M['NominalExpected'] = pct(exp_nominal, 1)
    M['RealizedOverNominal'] = pct((100 * ex_kn / events) / nominal_pct, 1)
    M['ExceedOld'] = pct(100 * ex_old / events, 1); M['FamFireOld'] = str(fam_old)
    M['GaussOld'] = pct(100 * 2 * NormalDist().cdf(-K_OLD / 2 ** 0.5), 1)
    for key, name in (('LogEight', 'boot_log8.txt'), ('LogTwelve', 'boot_log12.txt')):
        e, n = per_log[name]
        M[key + 'Exceed'] = str(e); M[key + 'Events'] = str(n); M[key + 'Pct'] = pct(100 * e / n)

    # ===== (2) calibration: L1 (boot_log12, S1) and L2 (boot_log15, S2) =====
    for key, name in (('LOne', 'boot_log12.txt'), ('LTwo', 'boot_log15.txt')):
        b = parse(L + name)[0]; p = post(b)
        T0 = p[0]; n = len(T0); sd = statistics.stdev(T0); kn = k_n(n); ds = kn * sd
        iters = sorted((b[c][0][1], statistics.fmean(p[c])) for c in p)
        slope = ols_slope([i for i, _ in iters], [m for _, m in iters])
        xs = [b[c][0][1] for c in p for _ in p[c]]; ys = [d for c in p for d in p[c]]
        print(f'# {name}: slope on condition means {slope:.3f}, on all samples {ols_slope(xs, ys):.3f}')
        slo, shi = sigma_ci(sd, n)
        M['Sig' + key] = grp(sd); M['N' + key] = str(n); M['K' + key] = f'{kn:.3f}'
        M['Dstar' + key] = grp(ds); M['Slope' + key] = f'{slope:.3f}'
        M['Sig' + key + 'Lo'] = grp(slo); M['Sig' + key + 'Hi'] = grp(shi)
        M['Dstar' + key + 'Lo'] = grp(kn * slo); M['Dstar' + key + 'Hi'] = grp(kn * shi)
        M['Dstar' + key + 'RelLo'] = f'{100 * (1 - slo / sd):.0f}'; M['Dstar' + key + 'RelHi'] = f'{100 * (shi / sd - 1):.0f}'
        # sweep at k_n: smallest mean shift (in sigma) at which the clause fires
        fired = [(statistics.fmean(p[c][:len(T0)]) - statistics.fmean(T0)) / sd
                 for c in p if c != 0 and clause(T0, p[c], kn)[0] > 0]
        M['MinShift' + key] = f'{min(fired):.2f}' if fired else 'n/a'
    for n_, key in ((39, 'KThirtyNine'), (100, 'KHundred'), (108, 'KHundredEight')):
        M[key] = f'{k_n(n_):.3f}'

    # ===== (3) demonstration: silent (CST_Demonstration5) and naive (CST_Demonstration3) =====
    ps = post(parse(L + 'CST_Demonstration5.txt')[0]); pn = post(parse(L + 'CST_Demonstration3.txt')[0])
    so, sc = ps[0], ps[1]; n = len(so); sd = statistics.stdev(so); kn = k_n(n); ds = kn * sd
    slo, shi = sigma_ci(sd, n); sig = statistics.fmean(sc) - statistics.fmean(so)
    M['SigDemo'] = grp(sd); M['NDemo'] = str(n); M['KDemo'] = f'{kn:.3f}'; M['DstarDemo'] = grp(ds)
    M['SigDemoLo'] = grp(slo); M['SigDemoHi'] = grp(shi)
    M['SigDemoRelLo'] = f'{100 * (1 - slo / sd):.1f}'; M['SigDemoRelHi'] = f'{100 * (shi / sd - 1):.1f}'
    M['SigSilent'] = grp(sig); M['SigSilentRatio'] = f'{sig / ds:.3f}'; M['SigSilentNs'] = f'{sig / GHZ:.0f}'
    M['SilentMaxExceed'] = str(sum(1 for x, y in zip(so, sc) if abs(y - x) > ds))
    no, nc = pn[0], pn[1]; nsig = statistics.fmean(nc) - statistics.fmean(no)
    M['NNaive'] = str(min(len(no), len(nc))); M['SigNaive'] = grp(nsig); M['SigNaiveRatio'] = grp(nsig / ds)
    M['SdNaive'] = grp(statistics.stdev(no)); M['SigNaiveMcyc'] = f'{nsig / 1e6:.1f}'; M['SigNaiveMs'] = f'{nsig / GHZ / 1e6:.2f}'
    M['DstarDemoOld'] = grp(K_OLD * sd); M['SigSilentRatioOld'] = f'{sig / (K_OLD * sd):.3f}'; M['SigNaiveRatioOld'] = grp(nsig / (K_OLD * sd))
    # per-event exceedances of the silent-hook pair at Dstar (the clause, not the mean)
    sx = sum(1 for x, y in zip(so, sc) if abs(y - x) > ds); slo_, shi_ = cp_ci(sx, n)
    M['SilentExceed'] = str(sx); M['SilentExceedPct'] = pct(100 * sx / n, 1)
    M['SilentExceedLo'] = pct(100 * slo_, 1); M['SilentExceedHi'] = pct(100 * shi_, 1)
    # cross-boot probe of the synthetic guest: cond-0 post-warm-up samples pooled over its boots
    cb = parse(L + 'CST_Demonstration4.txt'); pooled = [d for b in cb for d in post(b).get(0, [])]
    M['NBootsDemoCross'] = str(len(cb)); M['NDemoCross'] = str(len(pooled)); M['SigDemoCross'] = grp(statistics.stdev(pooled))

    # ===== (4) envelopes (App. D): structural = eps + delta_A1 + a, timing = delta_A1 + 2a, delta_A1 = eps =====
    ar = 100 * ex_kn / events
    for key, eps in (('Within', EPS_WITHIN_PCT), ('Cross', EPS_CROSS_PCT)):
        M['Env' + key + 'Struct'] = pct(2 * eps + ar); M['Env' + key + 'Timing'] = pct(eps + 2 * ar)
    M['EpsWithin'] = pct(EPS_WITHIN_PCT); M['EpsCross'] = pct(EPS_CROSS_PCT, 1)
    # two claims of opposite witness (within-boot): mixed-witness aggregate vs the naive 2x worst-clause bound
    M['EnvWithinPair'] = pct((2 * EPS_WITHIN_PCT + ar) + (EPS_WITHIN_PCT + 2 * ar))
    M['EnvWithinNaive'] = pct(2 * (EPS_WITHIN_PCT + 2 * ar))

    # ===== (5) Gaussian power: mean shift (in sigma) at which the clause fires on half the traces, n = 108 =====
    def fam_power(mu, n_, k):
        pe = NormalDist().cdf(-(k - mu) / 2 ** 0.5) + NormalDist().cdf(-(k + mu) / 2 ** 0.5)
        return 1 - (1 - pe) ** n_
    lo_, hi_ = 0.0, 10.0
    for _ in range(60):
        mid = (lo_ + hi_) / 2
        if fam_power(mid, 108, k_n(108)) < 0.5: lo_ = mid
        else: hi_ = mid
    M['ShiftHalf'] = f'{(lo_ + hi_) / 2:.1f}'

    with open(a.out, 'w') as f:
        f.write('% extp_numbers.tex -- GENERATED by measurements/gen_numbers.py from the raw logs; do not edit.\n')
        f.write(f'% alpha = {ALPHA}, warm-up = {WARMUP}, eps_SOE (within/cross, %) = {EPS_WITHIN_PCT}/{EPS_CROSS_PCT} (sec:capsep)\n')
        for k, v in M.items():
            f.write(f'\\newcommand{{\\{k}}}{{{v}}}\n')
    for k, v in M.items(): print(f'{k:22s} {v}')
    print(f'-- wrote {len(M)} macros to {a.out}')

if __name__ == '__main__':
    main()
