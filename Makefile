.PHONY: test preflight starter-failure hidden-starter-failure matrix validate-template validate-template-rejects-placeholders scorecard-example clean-generated

test: preflight

preflight:
	python -m pytest benchmark_harness/tests -q

scorecard-example:
	@bundles="$$(find . -maxdepth 1 \( -name '*-eval-bundle.tar.gz' -o -name '*-initial-fail-bundle.tar.gz' \) | sort)"; \
	if [ -z "$$bundles" ]; then \
		echo "No local bundles found. Unpack benchmark bundles next to the repo and try again."; \
		exit 1; \
	fi; \
	python -m benchmark_harness.scorecard $$bundles

clean-generated:
	rm -rf benchmark-data local_plugins .pytest_cache .venv agent_workflow_bench.egg-info benchmark_v04_pilot_harness.egg-info
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find tasks -type d -path '*/starter_repo/outputs' -exec rm -rf {} +
	find . -maxdepth 1 \( -name '*-eval-bundle.tar.gz' -o -name '*-initial-fail-bundle.tar.gz' \) -delete

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
