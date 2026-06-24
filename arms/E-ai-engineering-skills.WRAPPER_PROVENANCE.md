# Wrapper Provenance

## Arm
- Arm ID: E
- Arm name: ai-engineering-skills

## Source repository
- Repo URL: private ai-engineering-skills git URL supplied by the runner
- Pinned commit SHA: TO_BE_PINNED_BY `benchmark_harness/scripts/pin_skill_repos.sh`
- Date pinned: TO_BE_FILLED_BY_RUNNER

## Source files consulted
| File | Commit SHA | Relevant sections |
|---|---|---|
| README.md | TO_BE_PINNED | Bounded scope, mini-specs, one-task builds, verification, handoff |
| AGENTS.md | TO_BE_PINNED | Agent workflow guidance |
| skills/* | TO_BE_PINNED | Native skill workflows |

## Instructions copied or adapted
| Source file | Source wording / concept | Wrapper wording | Adaptation rationale |
|---|---|---|---|
| README.md / skill names | mini-spec, scope-freeze, build-one, test-mini, verify-contract, handoff, diagnose-loop, bug-capture | Lists documented workflow names | Activates native workflow vocabulary without task-specific answers |

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
