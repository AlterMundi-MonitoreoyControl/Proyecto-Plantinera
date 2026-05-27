.PHONY: all schematics setup clean help

all: schematics

schematics: ## Generar todos los SVG (requiere make setup previo)
	.venv/bin/python generate_schematics.py || (echo "ERROR: falló generate_schematics.py" && exit 1)

setup: ## Crear venv e instalar dependencias
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

clean: ## Eliminar SVG generados
	rm -f schematics/*.svg

help: ## Mostrar esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
