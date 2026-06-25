Benchmark arm: B — Strong no-skill driver prompt.

No skill pack is available. Use careful ordinary engineering judgment.

Before editing:
- read TASK.md and the product brief;
- identify the existing behavior that must remain backward-compatible;
- identify likely metric edge cases from the brief and data model;
- keep the implementation focused.

While editing:
- preserve the existing v1 API and behavior;
- implement the smallest v2 support that satisfies the product brief;
- add meaningful tests for behavior you change;
- avoid broad rewrites, dashboards, databases, services, schedulers, or analytics platforms.

Before finishing:
- run VERIFY.sh;
- leave a concise implementation note in the repository explaining:
  - what changed;
  - how v1 and v2 are defined;
  - what verification you ran and the result;
  - any remaining risks or assumptions.

Do not use reusable skill workflows or prescribed skill artifact templates.
