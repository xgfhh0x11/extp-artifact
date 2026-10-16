# Changelog

## Version 2 — October 2026 — doi:10.5281/zenodo.23403670

Version 1 (September 2026, doi:10.5281/zenodo.22849591) remains available on
Zenodo and is superseded by this version. It contained the following errors;
every proof is parametric in the threshold Δ* and is unchanged.

1. **False-positive rate measured with the wrong statistic.** Version 1
   reported realized false-positive rates of 0.61 % (L1) and 2.78 % (L2) for the
   timing clause. Those rates came from a per-sample, one-sided test
   (`x_i > mean + 1.645·σ`, script `analyze_l2_sweep.py`), not from the
   pair-difference clause `|Δ_cf,i − Δ_orig,i| > Δ*` that the divergence
   predicate D, the coincidence lemma and the Isabelle model define.
2. **The version-1 threshold fires on every trace.** Version 1 set
   Δ* = 1.645·σ, the one-sided 95 % Gaussian quantile applied per event.
   Evaluated with the clause itself on the 74 zero-intervention pairs of §MI,
   that threshold exceeds on 23.4 % of events (Gaussian prediction
   2Φ(−1.645/√2) = 24.5 %) and fires on 74 of 74 traces, so the "no divergence"
   verdict ¬D was unattainable on any trace. Version 2 uses a family-wise
   threshold Δ* = k_n·σ with k_n = √2·z_{1−α/(2n)} (α = 0.05; k_39 = 4.554,
   k_100 = 4.923, k_108 = 4.952) and reports the rates it actually produces:
   per-event 0.69 % (Clopper–Pearson 95 % CI [0.44, 1.04] %; Gaussian nominal
   0.11 %, i.e. about 6× heavier tail) and family-wise 24.3 % (CI [15.1, 35.7] %)
   against the nominal 5 %. The excess is a low-side tail that coincides with no
   recorded marker; its source is left open.
3. **Sample count.** `boot_log15` (L2-pchase) has n = 39 post-warm-up samples per
   condition, not 108 as stated; σ was correct.
4. **Derived values.** Calibrated thresholds 9,077 / 7,574 / 10,259 cycle became
   27,322 / 20,966 / 30,699 cycle; the L1 slope 4.481 became 4.519 cycle/iter
   (least squares on condition means); the demonstration signature ratios
   0.033·Δ* (silent hook) and 2,595·Δ* (naïve hook) became 0.011·Δ* and 867·Δ*;
   the witness envelopes of Appendix D, 1.35 %/1.59 % (within-boot) and
   21.41 %/11.62 % (cross-boot), became 1.43 %/1.76 % and 21.49 %/11.79 %.
   Table V and both demonstration figures were regenerated.

Post-release text edit (2026-10-15, same version): the related-work section now
positions CST against VM replay for intrusion analysis (ReVirt, TTVM, REPT) and
symbolic root-cause analysis of exploits (ARCUS), and cites concurrent SCM-replay
work outside security, Chakraborty–Caulfield–Pym's intervention logic, and Cock
et al.'s seL4 timing-channel measurements. No number, proof or claim scope changed. A consistency pass the same day replaced the
last two version-1 envelope figures in the body (1.35 %, 2.94 %/3.18 %) with the
generated values, restated the silent-hook result per event (2 of 100 events exceed
Δ*, consistent with α_realized) instead of as a mean-level "subthreshold" claim, and
aligned the instrument-policy, scope and cross-reference wording; `CST_Demonstration4.txt`
(cross-boot probe, σ = 5,614) added to `logs/` and `gen_numbers.py`.

Version 2.1 wording (2026-10-16, same record): the threshold is now *defined* as the
rational table value k_hat_n = floor(k_n * 2^16) / 2^16; the Gaussian family-wise quantile
k_n is the table's motivation, not a definition. Every script reads the table
(`measurements/kn_table.py`); re-running all v2 measurements with the table value changes
no reported number (the generated macro file is byte-identical). The table is verified by an
independent 50-digit mpmath recomputation (`measurements/verify_kn_table.py`, 0 mismatches
for n <= 4096). The CMD mechanization that imports CST no longer needs an irrational k_n or
a bracket axiom.

Version 2.1 wording, second edit (2026-10-16, same record): the silent-hook
demonstration states its unit explicitly (one aligned sample pair per event, all
within a single trace) and counts events; next to the family-wise rate, the MI
section and the demonstration now quote the trace-level silence rate, the
zero-intervention traces on which the clause never fires (56/74, 75.7 %,
Clopper-Pearson [64.3, 84.9] %), emitted by `gen_numbers.py` as
`TraceSilentKn/Rate/Lo/Hi`. No measured number changed.

Artifact changes:

- `logs/`: all raw boot logs added (17 boot logs + 2 demonstration logs,
  ~16 MB), so the lemma's quantity can be recomputed from source.
- `measurements/gen_numbers.py`: derives every measured number in the paper
  from the logs and emits them as LaTeX macros (`extp_numbers.tex`); the paper
  source includes that file instead of hand-copied literals.
- `measurements/analyze_pair_clause.py`, `tail_check.py`, `gen_kn_table.py`
  and their outputs added.
- `paper/extp.pdf`: version 2 (Appendix "Erratum to Version 1").

## Version 1 — September 2026

Initial release: Isabelle/HOL mechanization, measurement summaries, boot
protocols, boot images, figures, preprint PDF.
