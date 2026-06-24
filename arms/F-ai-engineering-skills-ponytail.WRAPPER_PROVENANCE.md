# Wrapper Provenance

## Arm
- Arm ID: F
- Arm name: ai-engineering-skills + Ponytail

## Source repository
- Repo URL: private ai-engineering-skills git URL supplied by the runner and https://github.com/DietrichGebert/ponytail
- Pinned commit SHA: TO_BE_PINNED_BY `benchmark_harness/scripts/pin_skill_repos.sh`
- Date pinned: TO_BE_FILLED_BY_RUNNER

## Source files consulted
| File | Commit SHA | Relevant sections |
|---|---|---|
| ai-engineering-skills README.md | TO_BE_PINNED | Bounded workflow, verification, handoff |
| Ponytail README.md | TO_BE_PINNED | Minimality / avoid overbuild |
| Ponytail skills/ponytail/SKILL.md | TO_BE_PINNED | Simplest working solution |

## Instructions copied or adapted
| Source file | Source wording / concept | Wrapper wording | Adaptation rationale |
|---|---|---|---|
| Both repos | ai-engineering-skills for bounded workflow; Ponytail for minimality | Explicitly composes the two native purposes | This is the only combined arm, so composition is stated rather than hidden |

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
