# Rota Fluminense - Back-end

API Flask do projeto Rota Fluminense para consultar e administrar locais
turísticos do estado do Rio de Janeiro e suas avaliações, com persistência em
MySQL, migrações Alembic, previsão meteorológica pelo Open-Meteo e documentação
OpenAPI.

## Visão geral e tecnologias

O back-end é o componente central do MVP: publica as dez operações da API,
mantém o MySQL como fonte de verdade, serve o contrato OpenAPI e encapsula a
consulta ao Open-Meteo. O navegador nunca acessa o banco nem o provedor
meteorológico diretamente.

| Camada | Tecnologias principais |
| --- | --- |
| API e contrato | Python 3.10+, Flask 3, flask-openapi3 e Pydantic 2 |
| Persistência | SQLAlchemy 2, PyMySQL, MySQL 8.4.11 e Alembic |
| Integração externa | HTTPX e Open-Meteo Weather Forecast API |
| Execução | Gunicorn, Docker e Docker Compose |
| Qualidade | unittest, coverage, Black, isort, Flake8 e pydocstyle |

## Arquitetura

![Diagrama da arquitetura do Rota Fluminense](docs/arquitetura/arquitetura-rota-fluminense.svg)

O navegador recebe o bundle React servido pelo Nginx em `127.0.0.1:5173` e
chama a API Flask/Gunicorn em `127.0.0.1:5000`. A origem do front-end precisa
estar em `CORS_ALLOWED_ORIGINS`. A API acessa o MySQL pela rede interna
`backend` e consulta o Open-Meteo por HTTPS; o MySQL não publica porta no fluxo
principal. `VITE_API_URL` é resolvida pelo navegador e, portanto, deve apontar
para a URL pública da API, nunca para o hostname Compose `backend`.

## Início rápido

Com os repositórios back-end e front-end em diretórios irmãos, Docker ativo e
um `.env` criado a partir de `.env.example`:

```powershell
docker compose --env-file .env config --quiet
docker compose --env-file .env up --build --detach --wait
docker compose --env-file .env ps
```


Abra `http://localhost:5173` e o Swagger em
`http://localhost:5000/openapi/`. Para encerrar sem apagar os dados:

```powershell
docker compose --env-file .env down
```


## Documentação da API

- Swagger da aplicação em execução: `http://127.0.0.1:5000/openapi/`.
- Documento OpenAPI em JSON: `http://127.0.0.1:5000/openapi/openapi.json`.
- Contrato implementado até o Dia 4: [`docs/CONTRATO_API.md`](docs/CONTRATO_API.md).
- Comandos reproduzíveis de operação: [`docs/COMANDOS.md`](docs/COMANDOS.md).
- Guia rápido para iniciar e testar: [`docs/INSTRUCOES_START_BACKEND_E_TESTES.md`](docs/INSTRUCOES_START_BACKEND_E_TESTES.md).
- Roteiro automatizado e checklist do Dia 6: [`docs/implementacoes/dia-6-conteinerizacao-completa/INSTRUCOES_TESTES_INTEGRADOS_DIA_6.md`](docs/implementacoes/dia-6-conteinerizacao-completa/INSTRUCOES_TESTES_INTEGRADOS_DIA_6.md).
- Resumo da API de locais e avaliações: [`docs/implementacoes/dia-3-api-locais-e-avaliacoes/RESUMO_dia_3_api_de_locais_e_avaliacoes.md`](docs/implementacoes/dia-3-api-locais-e-avaliacoes/RESUMO_dia_3_api_de_locais_e_avaliacoes.md).
- Resumo da integração meteorológica: [`docs/implementacoes/dia-4-servico-open-meteo/RESUMO_dia_4_servico_open_meteo.md`](docs/implementacoes/dia-4-servico-open-meteo/RESUMO_dia_4_servico_open_meteo.md).
- Implementação de MySQL, migrações e seed: [resumo](docs/implementacoes/dia-2-mysql-migracoes-e-seed/RESUMO_dia_2_mysql_migracoes_e_seed.md) e [plano detalhado](docs/implementacoes/dia-2-mysql-migracoes-e-seed/TODO_dia_2_mysql_migracoes_e_seed.md).
- Conteinerização completa: [resumo do Dia 6](docs/implementacoes/dia-6-conteinerizacao-completa/RESUMO_dia_6_conteinerizacao_completa.md) e [plano detalhado](docs/implementacoes/dia-6-conteinerizacao-completa/TODO_dia_6_conteinerizacao_completa.md).

O Swagger e o contrato estão alinhados para as dez operações canônicas
entregues até o Dia 4, incluindo a consulta de clima atual e previsão de três
dias pelo `slug` de um local.

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
- Consulta climática por `slug`, com condições atuais, previsão de três dias,
  tradução dos códigos WMO, cache com TTL e degradação segura.
- Seed idempotente com seis locais e seis avaliações curadas.

## Pré-requisitos

- Python 3.10 ou superior.
- Docker Desktop ou Docker Engine com o plugin Compose.
- Git para clonar o repositório.

Para a pilha completa, mantenha os repositórios irmãos sob o mesmo diretório:

```text
<diretorio-de-trabalho>/
├── rota-fluminense-backend/
└── rota-fluminense-front-end-avancado/
```


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
| `OPEN_METEO_TIMEOUT_SECONDS` | Timeout externo em segundos; padrão `5`, intervalo de `0.1` a `30`. |
| `OPEN_METEO_CACHE_TTL_SECONDS` | TTL do cache em segundos; padrão `1800`, intervalo de `1` a `86400`. |

`CORS_ALLOWED_ORIGINS` é obrigatória e aceita uma lista separada por vírgulas
de origens HTTP/HTTPS explícitas, por exemplo
`http://localhost:5173,https://app.exemplo.test`. Não use caminho, consulta,
fragmento, credenciais, `null` ou `*`. A ausência ou invalidade impede a
inicialização sem registrar o valor recebido. Uma origem não autorizada não
recebe `Access-Control-Allow-Origin`; isso limita chamadas feitas por
navegadores, mas não autentica clientes diretos nem protege as rotas de escrita.

As duas configurações meteorológicas são validadas na inicialização. Valores
vazios, malformados ou fora dos intervalos impedem a aplicação de iniciar. A
API pública gratuita do Open-Meteo não exige chave neste MVP.

O `docker-compose.yml` é o fluxo principal: constrói front-end e back-end,
mantém o MySQL apenas na rede interna e monta a `DATABASE_URL` do contêiner com
o hostname `mysql`. A `DATABASE_URL` do `.env` é usada somente no fluxo nativo
alternativo, em conjunto com `compose.mysql-host-access.example.yml`.

Para o fluxo nativo, carregue a URL no terminal sem imprimi-la:

```powershell
$envConfig = ConvertFrom-StringData -StringData (Get-Content .env -Raw)
$env:DATABASE_URL = $envConfig.DATABASE_URL
```


Se a porta local do override for alterada, atualize `MYSQL_HOST_PORT` e a porta
presente em `DATABASE_URL`.

## Execução recomendada via Docker Compose

Na raiz deste repositório, construa e suba toda a pilha:

```powershell
docker compose --env-file .env config --quiet
docker compose --env-file .env up --build --detach --wait
docker compose --env-file .env ps
```


O entrypoint do back-end aplica as migrações e reconcilia o seed antes de
iniciar o Gunicorn. Aguarde os três serviços ficarem `healthy` e acesse:

- interface: `http://localhost:5173`;
- API: `http://localhost:5000`;
- Swagger: `http://localhost:5000/openapi/`;
- OpenAPI JSON: `http://localhost:5000/openapi/openapi.json`.

Para acompanhar a inicialização do back-end:

```powershell
docker compose --env-file .env logs -f backend
```


Interrompa a exibição com `Ctrl+C`; isso não para os serviços. Para encerrar a
pilha preservando o banco:

```powershell
docker compose --env-file .env down
```


Não acrescente `--volumes` se quiser manter os dados. Esse sinalizador remove o
volume nomeado do MySQL e apaga os dados persistidos.

## Fluxo nativo alternativo

Use este fluxo somente quando precisar executar Python e Vite diretamente no
host. Ele exige o override explícito que publica o MySQL apenas no loopback.

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
Invoke-WebRequest "$apiBaseUrl/openapi/" | Select-Object StatusCode
Invoke-RestMethod "$apiBaseUrl/openapi/openapi.json" | Select-Object openapi, info
Invoke-RestMethod "$apiBaseUrl/locais?pagina=1&por_pagina=12&ordenar_por=nome_asc"
Invoke-RestMethod "$apiBaseUrl/locais/arpoador"
Invoke-RestMethod "$apiBaseUrl/locais/arpoador/avaliacoes"
Invoke-RestMethod "$apiBaseUrl/locais/arpoador/clima"
```


Essas verificações são somente leitura. Consulte o contrato e o Swagger antes
de testar operações de escrita, pois elas alteram o banco e não exigem
autenticação neste MVP.

## Integração com o Open-Meteo

A rota `GET /locais/<slug>/clima` consulta o endpoint HTTPS fixo
`/v1/forecast` da Weather Forecast API usando exclusivamente as coordenadas
curadas do local persistido. Ela não aceita coordenadas, timezone, horizonte ou
variáveis meteorológicas pela requisição pública.

A integração solicita:

- clima atual: `temperature_2m`, `apparent_temperature`, `precipitation`,
  `weather_code` e `wind_speed_10m`;
- previsão diária: `temperature_2m_max`, `temperature_2m_min`,
  `precipitation_probability_max` e `weather_code`;
- `timezone=America/Sao_Paulo`, `forecast_days=3`, unidades métricas e datas em
  ISO 8601.

Somente respostas externas integralmente válidas entram no cache. O cache é
LRU, limitado a 256 entradas, local a cada processo e controlado por
`OPEN_METEO_CACHE_TTL_SECONDS`. Portanto, reiniciar a API ou usar múltiplos
processos cria caches independentes. Dados expirados nunca são devolvidos como
sucesso; sem renovação válida, a rota responde HTTP `503` com
`clima_indisponivel`. Ausência ou invalidade de coordenadas usa
`coordenadas_indisponiveis`, e falhas do MySQL permanecem
`banco_indisponivel`.

Dados meteorológicos por [Open-Meteo.com](https://open-meteo.com/). Consulte a
[documentação oficial da Weather Forecast API](https://open-meteo.com/en/docs),
os [termos vigentes](https://open-meteo.com/en/terms) e a
[licença CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). O MVP é educacional. Na consulta realizada em 23/09/2026, a API gratuita era
limitada a uso não comercial, sob CC BY 4.0, e informava limites de 600
chamadas por minuto, 5.000 por hora e 10.000 por dia. Como os termos podem
mudar, atribuição, licença, volume e plano aplicável devem ser reconferidos
antes de publicação, uso comercial ou mudança relevante de tráfego.

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
| Aplicação não inicia após configurar clima | Confirme que timeout e TTL contêm números dentro dos intervalos documentados. |
| `coordenadas_indisponiveis` | Confirme que o local possui latitude e longitude válidas no MySQL e reconcilie o seed se necessário. |
| `clima_indisponivel` | Verifique internet, DNS, TLS e disponibilidade do Open-Meteo; a API não serve cache expirado. |

Substitua `docker compose ...` nas verificações pelo comando completo usado nas
seções anteriores. Os logs do MySQL podem conter dados operacionais sensíveis;
revise-os antes de compartilhar qualquer saída.

## Testes

```powershell
$databaseUrlAnterior = $env:DATABASE_URL
$corsAnterior = $env:CORS_ALLOWED_ORIGINS
try {
    $env:DATABASE_URL = "sqlite+pysqlite:///:memory:"
    $env:CORS_ALLOWED_ORIGINS = "http://localhost:5173"
    python -m unittest discover -s tests -v
    python -m coverage run --source=. --omit="tests/*,migrations/*,scripts/*" -m unittest discover -s tests
    python -m coverage report --show-missing
    python -m scripts.validate_e5_artifacts
} finally {
    $env:DATABASE_URL = $databaseUrlAnterior
    $env:CORS_ALLOWED_ORIGINS = $corsAnterior
}
```


O checkpoint do Dia 7 aprovou 267 testes e 97% de cobertura de linhas, sem
acesso real à internet. O validador confere contrato, Swagger, schemas,
arquivos JSON e links Markdown. Instale `coverage` no ambiente virtual se a
ferramenta ainda não estiver disponível.

A compatibilidade com o banco real é validada em um projeto Compose
descartável, separado do volume de desenvolvimento:

```powershell
.\scripts\run_mysql_integration.ps1
```


O script executa seis grupos funcionais, simula integralmente o Open-Meteo e
remove contêiner, rede e volume de teste tanto no sucesso quanto na falha. Ele
exige Docker e não deve deixar recursos com o projeto
`rota-fluminense-mysql-tests`. Comandos adicionais de qualidade e do front-end
estão em [`docs/COMANDOS.md`](docs/COMANDOS.md).

## Segurança e limites do MVP

- As rotas de escrita não têm autenticação, autorização, rate limiting ou
  proteção contra abuso; use apenas em ambiente local ou controlado.
- CORS é uma política do navegador, não um controle de acesso para clientes
  diretos. TLS, WAF e gestão externa de segredos permanecem fora do escopo.
- O cache climático vive em memória e não é compartilhado entre processos.
- O MySQL não publica porta no fluxo Compose principal; o override nativo o
  vincula somente ao loopback.

O modelo de ameaças e a matriz das dez operações estão em
[`MATRIZ_VALIDACAO_E_MODELO_AMEACAS.md`](docs/implementacoes/dia-7-testes-seguranca-e-documentacao/MATRIZ_VALIDACAO_E_MODELO_AMEACAS.md).
## Autor

Leonardo Abreu Santos
