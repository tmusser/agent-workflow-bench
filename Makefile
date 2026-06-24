.PHONY: preflight starter-failure hidden-starter-failure matrix validate-template validate-template-rejects-placeholders

preflight:
	python -m pytest benchmark_harness/tests -q

starter-failure:
	cd tasks/04-impossible-churn/starter_repo && PYTHONPATH=src python -m pytest -q || true
	cd tasks/04-impossible-churn/starter_repo && PYTHONPATH=src python scripts/reproduce_churn_bug.py || true

hidden-starter-failure:
	python -m benchmark_harness.evaluators.task4_hidden_evaluator --repo tasks/04-impossible-churn/starter_repo || true

matrix:
	python -m benchmark_harness.create_run_matrix --out benchmark_harness/run_matrix.csv --repeats 2

validate-template:
	python -m benchmark_harness.validate_skill_runtime_proof --allow-template benchmark_harness/templates/SKILL_RUNTIME_PROOF_TEMPLATE.md

validate-template-rejects-placeholders:
	! python -m benchmark_harness.validate_skill_runtime_proof benchmark_harness/templates/SKILL_RUNTIME_PROOF_TEMPLATE.md
