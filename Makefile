.PHONY: clean test test-skills test-workflows test-script-requests test-local test-real test-real-suite test-real-cli

QUERY ?= 这是 Bamboo 真实端到端测试。请真实调用 todo_write 写入两项计划；调用 write 在项目目录下的 .bamboo/e2e-real-output.txt 写入 bamboo-real-e2e-token；调用 read 读取该文件；最终回答包含 bamboo-real-e2e-token 和文件路径。不要只口头说明，请真的调用工具。
MODEL ?=
PROJECT ?= $(CURDIR)
CASE ?=

test:
	python tests/run_real_query.py --suite tests/real_queries.yaml --project "$(PROJECT)" --model "$(MODEL)" $(if $(CASE),--case "$(CASE)",)

test-skills:
	python -m pytest bamboo/skills/buildin -q

test-workflows:
	python -m pytest bamboo/workflows/buildin -q

test-script-requests:
	python tests/run_script_requests.py

test-local: test-skills test-workflows

test-real:
	python tests/run_real_query.py --project "$(PROJECT)" --model "$(MODEL)" --query "$(QUERY)"

test-real-suite:
	python tests/run_real_query.py --suite tests/real_queries.yaml --project "$(PROJECT)" --model "$(MODEL)" $(if $(CASE),--case "$(CASE)",)

test-real-cli:
	python -m bamboo.run main --msg "$(QUERY)" --project "$(PROJECT)" --permission default --yes --no-stream $(if $(MODEL),--model "$(MODEL)",)

clean:
	@echo "Cleaning generated files..."
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info
	@echo "Clean complete."
