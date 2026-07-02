.PHONY: clean

clean:
	@echo "Cleaning generated files..."
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info
	@echo "Clean complete."
