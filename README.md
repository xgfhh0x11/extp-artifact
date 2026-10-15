# EXTp — artifact for "EXTp: A Soundness Theorem for Counterfactual Exploit Replay on Formally Verified Microkernels"

Utku Erol, Independent Researcher — utkuerol71@gmail.com

This repository accompanies the paper (preprint PDF in `paper/`). It contains the
Isabelle/HOL mechanization of the Counterfactual Soundness Theorem's conditional
core, the raw boot logs and the scripts that derive every measured number in the
paper from them, the seL4/EXTp VMM boot images used for the bare-metal runs, and
the paper figures.

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23403670.svg)](https://doi.org/10.5281/zenodo.23403670)

**Version 2 (October 2026, doi:10.5281/zenodo.23403670).** Version 1 (doi:10.5281/zenodo.22849591) reported false-positive rates measured
with a different statistic than the one the paper's lemma defines, and used a
per-event threshold that the lemma's own clause fires on in every trace. See
`CHANGELOG.md` for the list of corrections; the paper's Appendix "Erratum to
Version 1" states them in context.

## Contents

| Path | What it is |
|---|---|
| `isabelle/CST_Model.thy` | Isabelle/HOL development: 115 facts, no unproved obligations (`sorry`-free). Session `EXTp_CST`, built against Isabelle2025-1 + HOL-Library. |
| `isabelle/ROOT` | Session definition. |
| `isabelle/build_log.txt` | Output of the last `isabelle build` run (`Finished EXTp_CST`). |
| `logs/` | Raw serial-console boot logs (see below). |
| `measurements/gen_numbers.py` | Derives every measured number quoted in the paper from `logs/` and writes them as LaTeX macros (`extp_numbers.tex`, included by the paper source). Pure Python 3 stdlib. |
| `measurements/extp_numbers.tex` | The generated macro file the preprint was built with. |
| `measurements/analyze_pair_clause.py` (+ `.out`) | The per-event pair-difference timing clause evaluated on zero-intervention pairs at k = 1.645 (version 1) and at k_n (version 2); the source of the realized false-positive rates in §MI. |
| `measurements/tail_check.py` (+ `.out`) | Whether the events exceeding k_n·σ coincide with the markers recorded per sample (P-state, thermal status, APERF/MPERF). |
| `measurements/gen_kn_table.py` | Generates the Q16.16 rational table of k_n (rounded down) used by implementations. |
| `measurements/section6_summary.txt` | Numerical summary of the synthetic demonstration (version-1 thresholds; superseded by `extp_numbers.tex`). |
| `measurements/cross_boot_BOOT_INSTRUCTIONS.txt` | Cross-boot stability collection protocol and hardware identity (N=34 reported in the paper). |
| `measurements/demo_BOOT_INSTRUCTIONS.txt` | Counterfactual fuzzing sweep protocol (r8 varied across 33 curated values). |
| `binaries/demo/` | `kernel-x86_64-pc99` (seL4 microkernel ELF) and `extp-vmm-image-x86_64-pc99` (EXTp VMM rootserver) for the demonstration build (`EXTP_DEMO_BOOT=ON`, `EXTP_NUM_RUNS_OVERRIDE=222`). |
| `binaries/cross-boot/` | Same pair for the cross-boot stability build, plus `extp-vmm-image-x86_64-pc99.reset`, the state-reset utility image swapped in between collection rounds (see the cross-boot instructions). |
| `figures/` | The three evaluation figures as shipped in the paper. |
| `paper/extp.pdf` | Preprint (version 2). |

## Raw logs and the numbers derived from them

`logs/` holds every serial-console boot log collected on the box, unmodified
(May 2026). The timing samples are the `[EXTp][TIMING_RAW]` lines; the
`[EXTp][BOOT]`/`BOOT_START` lines separate boots.

| Log | Content |
|---|---|
| `boot_log8.txt` … `boot_log16.txt` | Single-boot calibration, sweep and demonstration runs with per-sample markers (`mperf_d`, `aperf_d`, `perf_status`, `therm`). `boot_log12` is the L1-pchase calibration (S1, n = 108), `boot_log15` the L2-pchase calibration (S2, n = 39), `boot_log14` the 4,500-iteration probe. |
| `boot_logN34_archive.txt` | The N = 34 cross-boot campaign reported in the paper. |
| `boot_logN100_final.txt` | The follow-up cross-boot campaign (29 boots collected before the hardware became unavailable). |
| `CST_Demonstration5.txt`, `CST_Demonstration3.txt`, `CST_Demonstration4.txt` | Silent-hook (n = 100 per condition) and naïve-hook (n = 23) demonstration runs of §Evaluation, and the 3-boot cross-boot probe of the synthetic guest (σ = 5,614, n = 69 pooled). |
| `boot_log.txt`, `boot_log2–4.txt`, `boot_log6.txt`, `boot_log7.txt` | First-day development runs: overlapping partial captures of an N = 20 campaign, a CMOS-only test, and the first single-boot instrument test. Shipped for completeness; not in the paper's set. |

The paper's zero-intervention set (§MI, the lemma's α_realized) is
`boot_log8–16` + `boot_logN34_archive` + `boot_logN100_final`: 74 boots,
3,313 event pairs. To reproduce every number in the paper:

```
python3 measurements/gen_numbers.py --logs logs --out extp_numbers.tex
```

Expected: per-event α_realized = 0.69 % (Clopper–Pearson 95 % CI [0.44, 1.04] %),
family-wise 18/74 = 24.3 % (CI [15.1, 35.7] %), Gaussian nominal per-event
0.11 %. Robustness check — the same statistic over *all* 17 logs
(`--set all`, 112 boots, 4,470 pairs): 0.65 % (CI [0.43, 0.93] %) per event,
20.5 % (CI [13.5, 29.2] %) family-wise. The conclusion does not depend on the
selection.

Before release the logs were scanned for identifying strings (IPv4/MAC
addresses, host names, user names, serial numbers, hosting-provider
identifiers): none were found, and nothing was masked or edited. Two
cosmetic artefacts of the serial capture are left as they are: two NUL bytes
at the start of `boot_log14.txt` and one in `CST_Demonstration3.txt`, and one
VMM banner line in `boot_log14.txt` whose label contains the Turkish word
*Deney* ("experiment").

## Reproducing the Isabelle check

```
isabelle build -d isabelle -v EXTp_CST
```

Expected final line: `Finished EXTp_CST`. The theory states A1–A4 as locale
hypotheses (`cst_assumptions`, `sel4_lifting`); the conditional theorem
(`cst_conditional`), the Halpern–Pearl AC2 witnesses, the composition axiom in
its W/K_fwk form, scope-completeness, and Proposition 1 (sequential, trace-threaded,
and parallel-ensemble) are proved from them. Consistency of the locales is
witnessed by explicit models (`cst_withinboot`, `cst_crossboot`). The paper's
Table "Correspondence between the proof of Appendix D and the Isabelle/HOL
development" maps each proof component to a fact name in this file. The proofs
are parametric in the threshold Δ*; the version-2 change of Δ* did not touch
them.

## Running the boot images

Bare metal only: Intel 12th Gen Core (Alder Lake), microcode 0x3e, ASUS Z690,
UEFI, P-state locked at 4.9 GHz, serial console at 115200 8N1. Boot
`kernel-x86_64-pc99` with `extp-vmm-image-x86_64-pc99` as the rootserver via a
multiboot-capable loader; see the `*_BOOT_INSTRUCTIONS.txt` files for the exact
build flags and the collection protocol. The images are the ones the reported
numbers were collected with; the VMM source tree is not part of this release.

## Status and limitations

- The cross-boot bound rests on N=34 trials (Clopper–Pearson one-sided 95% upper
  bound on per-run failure ≤ 10.4%). Larger N requires the hardware above, which
  is not currently available to the author; the paper states the bound as is.
- The realized family-wise false-positive rate of the timing clause (24.3 %) is
  well above the nominal 5 %: the empirical tail is heavier than the Gaussian
  quantile assumes. The excess is a low-side tail that matches none of the
  recorded markers; no interrupt or SMI counter was recorded, so its source is
  open (the next hardware round should log MSR 0x34, the VM-exit count, and the
  timestamp's position relative to the event, per sample). The paper reports
  the realized rates and propagates them.
- The mechanization covers the conditional core only. The seL4 abstract-machine
  lifting and the calibration-to-HOL interface are open, as discussed in the
  paper's Discussion section.

## Citation

```
@misc{erol2026extp,
  author = {Utku Erol},
  title  = {{EXTp}: A Soundness Theorem for Counterfactual Exploit Replay on Formally Verified Microkernels},
  year   = {2026},
  doi    = {10.5281/zenodo.23403670},
  note   = {Preprint, version 2. Artifact: https://github.com/xgfhh0x11/extp-artifact}
}
```

## License

Isabelle sources, instructions, scripts and measurement data (including the raw
logs): MIT (see `LICENSE`). The paper PDF is © 2026 Utku Erol, all rights
reserved; the seL4 kernel ELF is subject to the seL4 license (GPLv2) of the
seL4 project.
