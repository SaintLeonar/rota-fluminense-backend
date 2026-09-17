# Rota Fluminense - Back-end

API Flask do projeto Rota Fluminense para consultar e administrar locais
turísticos do estado do Rio de Janeiro e suas avaliações, com persistência em
MySQL, migrações Alembic e documentação OpenAPI.

## Documentação da API

- Swagger da aplicação em execução: `http://127.0.0.1:5000/openapi`.
- Documento OpenAPI em JSON: `http://127.0.0.1:5000/openapi/openapi.json`.
- Contrato implementado no Dia 3: [`docs/CONTRATO_API.md`](docs/CONTRATO_API.md).
- Comandos reproduzíveis de operação: [`docs/COMANDOS.md`](docs/COMANDOS.md).
- Guia rápido para iniciar e testar: [`docs/INSTRUCOES_START_BACKEND_E_TESTES.md`](docs/INSTRUCOES_START_BACKEND_E_TESTES.md).
- Resumo da API de locais e avaliações: [`docs/implementacoes/dia-3-api-locais-e-avaliacoes/RESUMO_dia_3_api_de_locais_e_avaliacoes.md`](docs/implementacoes/dia-3-api-locais-e-avaliacoes/RESUMO_dia_3_api_de_locais_e_avaliacoes.md).
- Implementação de MySQL, migrações e seed: [resumo](docs/implementacoes/dia-2-mysql-migracoes-e-seed/RESUMO_dia_2_mysql_migracoes_e_seed.md) e [plano detalhado](docs/implementacoes/dia-2-mysql-migracoes-e-seed/TODO_dia_2_mysql_migracoes_e_seed.md).

O Swagger e o contrato estão alinhados para as nove operações canônicas de
locais e avaliações entregues no Dia 3. A rota de clima e a integração com o
Open-Meteo permanecem planejadas para o Dia 4 e ainda não estão disponíveis.

> **Limitação de segurança do MVP:** as rotas de escrita ainda não possuem
> autenticação nem autorização. Execute a API somente em ambiente controlado
> de demonstração e não publique essas operações irrestritamente na internet.

## Funcionalidades disponíveis

- Listagem de locais com filtros por cidade, categoria e destaque, paginação,
  cinco ordenações estáveis e agregados derivados das avaliações.
- Consulta, criação, substituição completa e exclusão de local por `slug`.
- Listagem e criação de avaliações por `slug` do local; atualização parcial e
  exclusão de avaliação por identificador técnico.
- Erros no envelope canônico `erro`, com `requisicao_id` correlacionado ao
  cabeçalho `X-Request-ID` e distinção de indisponibilidade do banco.
- Seed idempotente com seis locais e seis avaliações curadas.

## Pré-requisitos

- Python 3.10 ou superior.
- Docker Desktop ou Docker Engine com o plugin Compose.
- Git para clonar o repositório.

Confirme as ferramentas antes de iniciar:

```powershell
python --version
docker version
docker compose version
```

## Instalação

```powershell
git clone <url-do-repositorio>
cd rota-fluminense-backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

No Linux ou macOS, ative o ambiente virtual com:

```bash
source .venv/bin/activate
```

## Configuração do ambiente

Crie o arquivo local de configuração a partir do exemplo e substitua os
valores demonstrativos:

```powershell
Copy-Item .env.example .env
```

O arquivo `.env` é ignorado pelo Git e não deve ser versionado. Use uma senha
exclusiva para o ambiente local. Se ela contiver caracteres reservados de URL,
codifique-os ao montar `DATABASE_URL`.

| Variável | Finalidade |
| --- | --- |
| `MYSQL_DATABASE` | Banco criado pelo contêiner MySQL. |
| `MYSQL_USER` | Usuário da aplicação. |
| `MYSQL_PASSWORD` | Senha do usuário da aplicação. |
| `MYSQL_RANDOM_ROOT_PASSWORD` | Solicita uma senha aleatória para `root`; mantenha `yes`. |
| `MYSQL_HOST_PORT` | Porta local do override; opcional, com padrão `3306`. |
| `DATABASE_URL` | URL SQLAlchemy obrigatória para API, Alembic e seed. |
| `APP_ENV` | Identifica o ambiente da aplicação. |
| `CORS_ALLOWED_ORIGINS` | Origem permitida para o front-end. |
| `OPEN_METEO_TIMEOUT_SECONDS` | Timeout planejado para o Open-Meteo. |
| `OPEN_METEO_CACHE_TTL_SECONDS` | TTL planejado para o cache meteorológico. |

O arquivo `docker-compose.yml` mantém o MySQL apenas na rede interna. Como a
API ainda roda no host, use também `compose.mysql-host-access.example.yml`, que
publica a porta somente em `127.0.0.1`.

O `.env.example` já usa `127.0.0.1` e a porta `MYSQL_HOST_PORT=3306`, pois a
API é executada no host nesta etapa. Carregue a URL no terminal sem imprimi-la:

```powershell
$envConfig = ConvertFrom-StringData -StringData (Get-Content .env -Raw)
$env:DATABASE_URL = $envConfig.DATABASE_URL
```

Se a porta local for alterada, atualize `MYSQL_HOST_PORT` e a porta presente em
`DATABASE_URL`. Quando o back-end for conteinerizado em uma etapa futura, a URL
do contêiner deverá usar o host interno `mysql`.

## Criação e execução local

1. Inicie o MySQL e aguarde o healthcheck:

```powershell
docker compose --env-file .env -f docker-compose.yml -f compose.mysql-host-access.example.yml up --detach --wait mysql
```

2. Exporte `DATABASE_URL` para o processo atual, conforme a seção anterior.

3. Aplique todas as migrações versionadas:

```powershell
python -m alembic upgrade head
python -m alembic current
```

A revisão esperada neste checkpoint é `1f9d5faddb44 (head)`. A aplicação não
cria tabelas automaticamente; um banco novo sempre precisa de `upgrade head`.

4. Execute o seed curado e idempotente:

```powershell
python -m scripts.seed
```

A primeira execução insere seis locais e seis avaliações. Execuções seguintes
mantêm o conteúdo e informam os 12 registros aprovados como ignorados.

5. Inicie a API:

```powershell
python app.py
```

6. Em outro terminal, valide a documentação e as consultas de leitura:

```powershell
$apiBaseUrl = "http://127.0.0.1:5000"
Invoke-WebRequest "$apiBaseUrl/openapi" | Select-Object StatusCode
Invoke-RestMethod "$apiBaseUrl/openapi/openapi.json" | Select-Object openapi, info
Invoke-RestMethod "$apiBaseUrl/locais?pagina=1&por_pagina=12&ordenar_por=nome_asc"
Invoke-RestMethod "$apiBaseUrl/locais/arpoador"
Invoke-RestMethod "$apiBaseUrl/locais/arpoador/avaliacoes"
```

Essas verificações são somente leitura. Consulte o contrato e o Swagger antes
de testar operações de escrita, pois elas alteram o banco e não exigem
autenticação neste MVP.

## Operação do banco e das migrações

### Inspecionar o estado

```powershell
docker compose --env-file .env -f docker-compose.yml -f compose.mysql-host-access.example.yml ps
python -m alembic current
python -m alembic history
python -m alembic check
```

Uma consulta de diagnóstico pode ser executada dentro do contêiner sem gravar
a senha no comando:

```powershell
docker compose --env-file .env -f docker-compose.yml -f compose.mysql-host-access.example.yml exec mysql sh -c 'MYSQL_PWD="$MYSQL_PASSWORD" mysql --host=127.0.0.1 --user="$MYSQL_USER" --database="$MYSQL_DATABASE" --execute="SELECT DATABASE(), VERSION(), 1"'
```

### Aplicar atualizações

Depois de atualizar o código, com o MySQL saudável e `DATABASE_URL` exportada:

```powershell
python -m alembic upgrade head
python -m alembic current
python -m scripts.seed
```

### Parar sem apagar os dados

```powershell
docker compose --env-file .env -f docker-compose.yml -f compose.mysql-host-access.example.yml stop mysql
```

Para remover contêiner e rede, preservando o volume nomeado:

```powershell
docker compose --env-file .env -f docker-compose.yml -f compose.mysql-host-access.example.yml down
```

### Recriar um banco local limpo

> Atenção: `down --volumes` apaga definitivamente os dados MySQL desse projeto
> Compose. Use apenas no ambiente local e confirme o diretório do projeto antes
> de executar.

```powershell
docker compose --env-file .env -f docker-compose.yml -f compose.mysql-host-access.example.yml down --volumes
docker compose --env-file .env -f docker-compose.yml -f compose.mysql-host-access.example.yml up --detach --wait mysql
python -m alembic upgrade head
python -m scripts.seed
```

### Executar downgrade controlado

Pare a API, confirme a revisão atual e faça backup de qualquer dado que precise
ser preservado. Não execute este fluxo em ambiente compartilhado ou de produção.

```powershell
python -m alembic current
python -m alembic history
python -m alembic downgrade base
```

Atualmente existe uma única revisão inicial. Por isso, `downgrade base` remove
as tabelas `avaliacoes` e `locais_turisticos` e todos os dados contidos nelas.
Para recriar o schema e restaurar somente o conteúdo curado:

```powershell
python -m alembic upgrade head
python -m scripts.seed
```

## Diagnóstico básico

| Sintoma | Verificação |
| --- | --- |
| Variável obrigatória ausente | Confirme `.env` para o Compose e `$env:DATABASE_URL` para os comandos Python. |
| Porta local ocupada | Defina outra `MYSQL_HOST_PORT` em `.env` e use a mesma porta em `DATABASE_URL`. |
| `Connection refused` | Execute `docker compose ... ps` e aguarde o estado `healthy`. |
| `Access denied` | Confirme usuário, senha e banco em `.env`; volumes existentes mantêm as credenciais da primeira criação. |
| Tabela inexistente | Execute `python -m alembic current` e depois `python -m alembic upgrade head`. |
| Seed não insere novamente | É o comportamento idempotente esperado; confira os totais `ignorados` do relatório. |

Substitua `docker compose ...` nas verificações pelo comando completo usado nas
seções anteriores. Os logs do MySQL podem conter dados operacionais sensíveis;
revise-os antes de compartilhar qualquer saída.

## Testes

```powershell
$env:DATABASE_URL = "sqlite+pysqlite:///:memory:"
python -m unittest discover -s tests -v
python -m unittest tests.test_openapi_documentation -v
python -m scripts.validate_e5_artifacts
```

O primeiro comando executa a regressão completa. Os dois últimos validam
especificamente a documentação OpenAPI e a conformidade entre contrato,
Swagger, schemas, arquivos JSON e links Markdown. Recarregue a `DATABASE_URL`
do `.env` antes de iniciar novamente a API contra o MySQL.

## Autor

Leonardo Abreu Santos
