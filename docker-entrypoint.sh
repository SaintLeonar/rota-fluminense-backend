#!/bin/sh
set -eu

echo "Aplicando migrações do banco de dados..."
python -m alembic upgrade head

echo "Reconciliando o seed idempotente..."
python -m scripts.seed

echo "Iniciando a aplicação..."
exec "$@"
