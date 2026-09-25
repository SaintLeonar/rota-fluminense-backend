# Integração com a API externa Open-Meteo

Este documento identifica a API externa utilizada pelo Rota Fluminense e
registra suas condições de uso, necessidade de cadastro e rotas efetivamente
consumidas.

## Visão geral

| Item | Definição adotada no projeto |
| --- | --- |
| Provedor | [Open-Meteo](https://open-meteo.com/) |
| API | [Weather Forecast API](https://open-meteo.com/en/docs) |
| Finalidade | Obter condições meteorológicas atuais e previsão de três dias para um local turístico |
| Modalidade usada | API gratuita/open-access para uso educacional e não comercial |
| Cadastro | Não é necessário |
| Autenticação | Não exige chave de API na modalidade gratuita utilizada pelo MVP |
| Formato | Requisição HTTP `GET` por HTTPS e resposta JSON |
| Consumidor | Somente o back-end; o navegador não chama o Open-Meteo diretamente |

## Licença e condições de uso

Os dados fornecidos pelo Open-Meteo são disponibilizados sob a licença
[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
Ela permite compartilhar e adaptar os dados, inclusive comercialmente, desde
que seja dado o crédito apropriado, seja incluído um link para a licença e
sejam indicadas eventuais alterações.

É importante distinguir a licença dos **dados** das condições de acesso ao
**serviço hospedado**. A API gratuita usada neste MVP é destinada a uso não
comercial, não possui garantia de disponibilidade e, segundo os termos
vigentes na data acima, está sujeita aos seguintes limites:

- 600 chamadas por minuto;
- 5.000 chamadas por hora;
- 10.000 chamadas por dia;
- 300.000 chamadas por mês.

O caráter educacional deste projeto é compatível com a modalidade gratuita.
Antes de qualquer uso comercial ou aumento relevante de volume, devem ser
reavaliados os [termos de uso](https://open-meteo.com/en/terms) e os
[planos comerciais](https://open-meteo.com/en/pricing). Os planos pagos usam
o domínio `customer-api.open-meteo.com`, exigem cadastro/assinatura e chave no
parâmetro `apikey`.

O código do servidor Open-Meteo é open source sob AGPLv3, mas essa licença do
software não substitui a CC BY 4.0 aplicável aos dados consumidos pelo projeto.

### Atribuição

O projeto deve manter uma atribuição visível próxima dos dados meteorológicos
ou na documentação/tela que os apresenta. Texto adotado:

> Dados meteorológicos por [Open-Meteo.com](https://open-meteo.com/), sob
> [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

O back-end traduz os códigos meteorológicos WMO para descrições e ícones
semânticos em português e reorganiza a resposta externa no contrato próprio da
aplicação. Portanto, essa transformação deve ser informada quando necessário
para cumprir a obrigação de indicar alterações da CC BY 4.0.

## Rotas utilizadas

### Rota externa

```http
GET https://api.open-meteo.com/v1/forecast
```

Essa é a única rota do Open-Meteo consumida pela aplicação. Não são utilizadas
as APIs de geocodificação, histórico, clima, qualidade do ar ou dados marinhos.
Latitude e longitude vêm do cadastro persistido de cada local turístico.

Parâmetros enviados:

| Parâmetro | Valor enviado | Finalidade |
| --- | --- | --- |
| `latitude` | Coordenada do local | Identificar a posição geográfica |
| `longitude` | Coordenada do local | Identificar a posição geográfica |
| `current` | `temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m` | Selecionar os dados atuais necessários |
| `daily` | `temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code` | Selecionar os dados diários necessários |
| `timezone` | `America/Sao_Paulo` | Retornar datas e horários no fuso adotado pelo projeto |
| `forecast_days` | `3` | Limitar a previsão a três dias |
| `temperature_unit` | `celsius` | Temperatura em graus Celsius |
| `wind_speed_unit` | `kmh` | Velocidade do vento em quilômetros por hora |
| `precipitation_unit` | `mm` | Precipitação em milímetros |
| `timeformat` | `iso8601` | Datas e horários em ISO 8601 |

Exemplo equivalente, com coordenadas ilustrativas:

```http
GET https://api.open-meteo.com/v1/forecast?latitude=-22.9887&longitude=-43.1934&current=temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code&timezone=America%2FSao_Paulo&forecast_days=3&temperature_unit=celsius&wind_speed_unit=kmh&precipitation_unit=mm&timeformat=iso8601
Accept: application/json
```

### Rota da API principal que expõe o resultado

```http
GET /locais/{slug}/clima
```

Exemplo local:

```http
GET http://127.0.0.1:5000/locais/arpoador/clima
```

O cliente informa apenas o `slug`. O back-end localiza as coordenadas no
MySQL, consulta o Open-Meteo, valida e transforma a resposta e devolve clima
atual e previsão de três dias no contrato da API principal. Coordenadas,
variáveis, unidades, fuso e quantidade de dias não podem ser alterados pelo
cliente nessa rota.

O contrato completo, exemplos de resposta e erros estão em
[`CONTRATO_API.md`](CONTRATO_API.md#clima-do-local--implementado-no-dia-4) e no
Swagger servido em `http://127.0.0.1:5000/openapi/` durante a execução.

## Cadastro, credenciais e segurança

Na configuração atual não há cadastro, token, segredo nem variável de ambiente
para chave do Open-Meteo. A chamada é identificada apenas pelo cabeçalho
`User-Agent: RotaFluminenseBackend/1.0`.

Caso o projeto migre para um plano comercial, a chave deverá ser tratada como
segredo de execução, nunca gravada no repositório, em imagens Docker, logs ou
respostas da API. Essa migração também exige trocar o domínio do provedor e
revisar o contrato comercial vigente.

## Cache e indisponibilidade

Para reduzir chamadas externas, o back-end mantém cache em memória por local,
com TTL padrão de 1.800 segundos, configurável por
`OPEN_METEO_CACHE_TTL_SECONDS`. O timeout padrão da chamada é de 5 segundos,
configurável por `OPEN_METEO_TIMEOUT_SECONDS`.

O cache é local a cada processo e dados expirados não são servidos. Quando não
há cache válido e o provedor apresenta timeout, erro de conectividade, status
HTTP inesperado ou resposta inválida, a rota principal retorna HTTP `503` com
o código seguro `clima_indisponivel`. A ausência ou invalidade das coordenadas
do local também impede a consulta externa.

## Referências oficiais

- [Página oficial do Open-Meteo](https://open-meteo.com/)
- [Documentação da Weather Forecast API](https://open-meteo.com/en/docs)
- [Termos de uso e privacidade](https://open-meteo.com/en/terms)
- [Planos, limites e perguntas frequentes](https://open-meteo.com/en/pricing)
- [Licença CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
