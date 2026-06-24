# Wrapper Provenance

## Arm
- Arm ID: D
- Arm name: Ponytail

## Source repository
- Repo URL: https://github.com/DietrichGebert/ponytail
- Pinned commit SHA: TO_BE_PINNED_BY `benchmark_harness/scripts/pin_skill_repos.sh`
- Date pinned: TO_BE_FILLED_BY_RUNNER

## Source files consulted
| File | Commit SHA | Relevant sections |
|---|---|---|
| README.md | TO_BE_PINNED | Minimalism / write less code |
| skills/ponytail/SKILL.md | TO_BE_PINNED | Lazy senior developer, simplest working solution |

## Instructions copied or adapted
| Source file | Source wording / concept | Wrapper wording | Adaptation rationale |
|---|---|---|---|
| README.md and skills/ponytail/SKILL.md | Best code is code not written; avoid over-engineering | "smallest change that works, reuse what exists, avoid unnecessary code" | Keeps native minimality thesis while protecting required tests and correctness |

## Instructions excluded
| Source file | Excluded instruction | Reason excluded |
|---|---|---|
| Any task-specific examples | Not used | Would leak hidden evaluator criteria or overfit Task 4 |
| Any unrelated install/marketplace instructions | Not used | Runtime installation is captured separately in `SKILL_RUNTIME_PROOF.md` |

## Subjective choices
- Wrapper includes only general workflow activation language, not task-specific hints.
- Wrapper is intentionally weaker than a full skill manual; the installed skill files are expected to provide full process detail.
- Final fairness depends on `SKILL_RUNTIME_PROOF.md` confirming the skill was installed and visible during the run.

## Hashes
- Wrapper file hash: TO_BE_FILLED_BY_RUNNER
- Provenance file hash: TO_BE_FILLED_BY_RUNNER
