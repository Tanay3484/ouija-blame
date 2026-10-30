# Results

45 deleted-then-restored lines from Rails, Kubernetes, Home Assistant, Ansible and Istio. Every method
saw only history from before the deletion. Grades were given blind to method.

| Method | Gives the revert's reason | Gives a recorded reason (any) | Median words to read |
|--------|---------------------------|-------------------------------|----------------------|
| git blame message | 7/45 (16%) | 19/45 (42%) | 12 |
| blame + its PR | 7/45 (16%) | 29/45 (64%) | 268 |
| git log -S, 5 oldest | 5/45 (11%) | 15/45 (33%) | 41 |
| séance | 8/45 (18%) | 28/45 (62%) | 67 |

Séance minus baseline, paired bootstrap (10,000 resamples of cases), 95% interval:

- vs git blame message, revert's reason: +0.02 (-0.04 to +0.09)
- vs git blame message, any recorded reason: +0.20 (+0.09 to +0.33)
- vs blame + its PR, revert's reason: +0.02 (-0.04 to +0.09)
- vs blame + its PR, any recorded reason: -0.02 (-0.11 to +0.04)
- vs git log -S, 5 oldest, revert's reason: +0.07 (-0.02 to +0.18)
- vs git log -S, 5 oldest, any recorded reason: +0.29 (+0.13 to +0.44)

- `git blame` showed the commit that first wrote the line in 28/45 cases; the walk always reaches it (median 1 commits per line).
- `git log -S` (5 oldest) included that commit in 29/45 cases.
- Answerable cases (some method surfaced a reason): 32/45.
- The séance stayed silent in 1/45: 1 of 13 unanswerable cases, and 0 answerable ones it missed.
- It spoke without giving a reason in 16 cases.
