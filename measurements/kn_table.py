"""kn_table.py -- THE threshold multiplier, single source for every script.

EXTp v2 defines the timing threshold as  Dstar = k_hat(n) * sigma_hat,  where
k_hat(n) = floor(k_n * 2^16) / 2^16  is a RATIONAL table value and
k_n = sqrt(2) * z_{1 - alpha/(2n)}  (alpha = 0.05) is the Gaussian family-wise
quantile that MOTIVATES the table.  The table is the definition; the formula
is where it came from.  Implementations (C reducer, Isabelle, every analysis
script) use k_hat, never the float k_n, so no irrational number enters any
decision or any reported number.

    kq16(n)   integer floor(k_n * 65536)            (0 for n < 2)
    k_hat(n)  Fraction(kq16(n), 65536)              exact rational
    k_float(n) float(k_hat(n))                       for plotting only

Cross-checked against an independent high-precision implementation
(verify_kn_table.py, mpmath, 50 digits) for n <= 4096.
"""
from fractions import Fraction
from math import floor
from statistics import NormalDist

ALPHA = 0.05
NMAX = 4096

def k_n_float(n, alpha=ALPHA):
    """Gaussian motivation only (double precision)."""
    return 2 ** 0.5 * NormalDist().inv_cdf(1 - alpha / (2 * n))

def kq16(n, alpha=ALPHA):
    if n < 2:
        return 0
    return floor(k_n_float(min(n, NMAX), alpha) * 65536)

def k_hat(n, alpha=ALPHA):
    return Fraction(kq16(n, alpha), 65536)

def k_float(n, alpha=ALPHA):
    return float(k_hat(n, alpha))

def k_hat_up(n, alpha=ALPHA):
    """Upper bracket (k_hat + 2^-16): the positive-polarity (PMU) threshold."""
    return Fraction(kq16(n, alpha) + 1, 65536)
