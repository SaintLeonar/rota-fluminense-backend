# Rota Fluminense - Back-end

Aplicação para consulta de locais turísticos do estado do Rio de Janeiro,
avaliações de visitantes e previsão do tempo. O projeto utiliza uma interface
React, uma API Flask, banco de dados MySQL e a API externa Open-Meteo.

## Tecnologias utilizadas

| Camada | Tecnologias |
| --- | --- |
| Front-end | React, Vite e Nginx |
| Back-end | Python, Flask e Gunicorn |
| Banco de dados | MySQL, SQLAlchemy e Alembic |
| API externa | Open-Meteo |
| Infraestrutura | Docker e Docker Compose |

## Documentação

Os documentos complementares estão disponíveis no diretório `docs/`:

- [Arquitetura Rota Fluminense](<docs/Arquitetura Rota Fluminense.pdf>):
  diagrama da arquitetura e da comunicação entre os componentes do projeto;
- [Integração com o Open-Meteo](docs/INTEGRACAO_OPEN_METEO.md): informações
  sobre a API externa, licença, cadastro e rotas utilizadas;
- [Instruções de teste do MVP](docs/INSTRUCOES_TESTE_MVP.md): passos para
  iniciar, validar e encerrar a aplicação.

## Pré-requisitos

- Docker Desktop ou Docker Engine com o plugin Compose para o fluxo recomendado.
- Python 3.10 ou superior e `pip` para testes ou execução nativa.
- Git para clonar os repositórios.
- Front-end `rota-fluminense-front-end-avancado`, construído automaticamente
  pelo Compose no fluxo principal.

Mantenha este repositório e `rota-fluminense-front-end-avancado` como
diretórios irmãos. O Compose de entrega fica em
`../rota-fluminense-front-end-avancado/docker-compose.yml` e usa este back-end
como contexto de build. Este repositório conserva um Compose equivalente para
compatibilidade operacional.

Por padrão, a API é publicada em `http://localhost:5000` e a interface em
`http://localhost:5173`.

## Instalação e execução

1. Clone os repositórios do back-end e do front-end no mesmo diretório:

```text
<diretorio-de-trabalho>/
├── rota-fluminense-backend/
└── rota-fluminense-front-end-avancado/
```

2. Entre no diretório do front-end, onde está o Compose de entrega:

```powershell
cd rota-fluminense-front-end-avancado
```

3. Crie o arquivo de configuração local:

```powershell
Copy-Item ../rota-fluminense-backend/.env.example ../rota-fluminense-backend/.env
```

Revise os valores de `../rota-fluminense-backend/.env`, principalmente usuário e senha do MySQL.

4. Construa as imagens e inicie a aplicação:

```powershell
docker compose --env-file ../rota-fluminense-backend/.env up --build --detach --wait
```

O Docker instala as dependências e inicia o front-end, o back-end e o MySQL.
Durante a inicialização, o back-end aplica as migrações e executa o seed
automaticamente. Não é necessário rodar um comando separado.

5. Acesse a aplicação:

- Interface: `http://localhost:5173`;
- API: `http://localhost:5000`;
- Swagger: `http://localhost:5000/openapi/`.

Para encerrar:

```powershell
docker compose --env-file ../rota-fluminense-backend/.env down
```

## Inicialização com inspeção HTTPS do antivírus

Use esta opção somente se um antivírus com inspeção de tráfego substituir o
certificado HTTPS do Open-Meteo e a consulta de clima apresentar erro de
certificado.

1. Abra o gerenciador de certificados do Windows com `certmgr.msc`.
2. Localize, em **Autoridades de Certificação Raiz Confiáveis**, o certificado
   usado pelo antivírus para inspeção HTTPS.
3. Exporte somente a parte pública, sem chave privada, no formato
   **X.509 codificado em Base-64**.
4. Salve o certificado fora do repositório, por exemplo em
   `C:\certificados\antivirus-root-ca.crt`.
5. Acrescente o caminho ao arquivo `../rota-fluminense-backend/.env`, usando barras `/`:

```dotenv
OPEN_METEO_CA_HOST_PATH=C:/certificados/antivirus-root-ca.crt
```

6. Inicie a aplicação com o arquivo de configuração adicional:

```powershell
docker compose --env-file ../rota-fluminense-backend/.env -f docker-compose.yml -f ../rota-fluminense-backend/compose.custom-ca.example.yml up --build --detach --wait
```

Esse modo monta o certificado somente no back-end e o adiciona às autoridades
confiáveis usadas na conexão com o Open-Meteo. A validação TLS permanece ativa.
Não versione o certificado e não desabilite a verificação HTTPS.

Para encerrar essa execução:

```powershell
docker compose --env-file ../rota-fluminense-backend/.env -f docker-compose.yml -f ../rota-fluminense-backend/compose.custom-ca.example.yml down
```

## Segurança e limitações do MVP

As rotas de escrita da API ainda não possuem autenticação ou autorização. Os
controles de editar e excluir não comprovam autoria nem restringem acesso;
servem exclusivamente à demonstração controlada do contrato HTTP. Execute o
conjunto somente em ambiente local ou controlado de demonstração.

`CORS_ALLOWED_ORIGINS` deve conter a origem pública do front-end, por padrão
`http://localhost:5173`. Uma origem negada não recebe autorização CORS. Essa
política protege apenas a fronteira do navegador e não substitui autenticação,
autorização, TLS ou limitação de requisições.

As portas públicas do Compose são vinculadas ao loopback e o MySQL não publica
porta por padrão. A gestão externa de segredos e o endurecimento para produção
permanecem fora do escopo deste MVP.

Dados meteorológicos por [Open-Meteo.com](https://open-meteo.com/).
