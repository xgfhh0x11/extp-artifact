#!/usr/bin/env python3
"""Independent recomputation of the k_n table with mpmath (50 digits).

Recomputes kq16(n) = floor(sqrt(2) * z_{1-alpha/(2n)} * 2^16) for 2 <= n <= NMAX
without statistics.NormalDist (uses mpmath's erfinv at 50-digit precision) and
compares with kn_table.py (double precision) and, if present, with the generated
C header and Isabelle theory.  Exit status 0 iff every entry agrees.
"""
import re, sys, os
import mpmath as mp
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kn_table

mp.mp.dps = 50
ALPHA = mp.mpf('0.05')

def kq16_mp(n):
    p = 1 - ALPHA / (2 * n)                 # upper-tail quantile level
    z = mp.sqrt(2) * mp.erfinv(2 * p - 1)   # z_p = sqrt(2) * erfinv(2p - 1)
    return int(mp.floor(mp.sqrt(2) * z * 65536))

def read_header(path):
    s = open(path, encoding='utf-8', errors='replace').read()
    body = s[s.index('{', s.index('extp_kn_q16')) + 1: s.index('};')]
    return [int(v) for v in re.findall(r'(\d+)u', body)]

def read_thy(path):
    s = open(path, encoding='utf-8', errors='replace').read()
    body = s[s.index('kq16_list = [') + len('kq16_list = ['): s.index(']"', s.index('kq16_list = ['))]
    return [int(v) for v in re.findall(r'\d+', body)]

def main():
    nmax = kn_table.NMAX
    bad = []
    mpv = [0, 0] + [kq16_mp(n) for n in range(2, nmax + 1)]
    dbl = [kn_table.kq16(n) for n in range(0, nmax + 1)]
    for n in range(nmax + 1):
        if mpv[n] != dbl[n]: bad.append(('double', n, dbl[n], mpv[n]))
    here = os.path.dirname(os.path.abspath(__file__))
    for name, reader, rel in (('C header', read_header, '../difftest/extp_kn_table.h'),
                              ('Isabelle', read_thy, '../CMD_Kn_Table.thy')):
        p = os.path.join(here, rel)
        if os.path.exists(p):
            vals = reader(p)
            if len(vals) != nmax + 1: bad.append((name, 'length', len(vals), nmax + 1))
            for n, v in enumerate(vals[:nmax + 1]):
                if v != mpv[n]: bad.append((name, n, v, mpv[n]))
        else:
            print('skip (not found):', p)
    # boundary margin: how close is any k_n*2^16 to an integer?  (reports the tightest cases)
    margins = []
    for n in range(2, nmax + 1):
        x = mp.sqrt(2) * mp.sqrt(2) * mp.erfinv(2 * (1 - ALPHA / (2 * n)) - 1) * 65536
        margins.append((float(x - mp.floor(x)), n))
    margins.sort()
    print(f'n <= {nmax}: mpmath vs double floor(k_n*2^16): {len([b for b in bad if b[0]=="double"])} mismatches')
    print('tightest fractional margins (frac part of k_n*2^16, n):', margins[:3], 'and', [(1-m, n) for m, n in margins[-3:]])
    for b in bad: print('MISMATCH', b)
    print('RESULT:', 'OK' if not bad else f'{len(bad)} MISMATCHES')
    sys.exit(1 if bad else 0)

if __name__ == '__main__':
    main()
