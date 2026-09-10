# Baseline A (shipping-gates campaign)

Frozen working plans: pre-placement Gemini + early silence polish.

- mean F1 @ ±15s: **0.755**
- min F1: **0.533**
- track |Δ|≤1: **100.0%**

| Show | F1 | tracks hyp/ref | Δ | match / near / far |
|------|----|----------------|---|--------------------|
| sbb2001-04-27.flac16 | 0.889 | 4/3 | +1 | 2 / 0 / 0 |
| los1997-04-03.kpig | 0.769 | 6/5 | +1 | 3 / 1 / 0 |
| ymsb2007-02-24.flac16 | 0.533 | 7/6 | +1 | 2 / 2 / 1 |
| crnml2002-08-30.flac16 | 0.783 | 11/10 | +1 | 7 / 1 / 1 |
| lke2006-11-10.early | 0.800 | 11/12 | -1 | 8 / 2 / 1 |

Plan copies live under `data/work/.baseline_a/` (gitignored media/work).
