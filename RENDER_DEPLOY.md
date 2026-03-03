# Deploy no Render

Este projeto ja esta preparado para deploy direto no Render.

Arquivos de deploy incluidos:
- `render.yaml`
- `.python-version`
- `requirements.txt`

## Opcao 1: Deploy automatico pelo `render.yaml`

Esse e o caminho mais simples.

1. Suba este projeto para o GitHub.
2. No Render, clique em `New` > `Blueprint`.
3. Conecte o repositorio.
4. O Render vai ler o arquivo `render.yaml`.
5. Revise o servico e clique para criar.

O que ja esta configurado no `render.yaml`:
- `type`: `web`
- `runtime`: `python`
- `region`: `oregon`
- `buildCommand`: `pip install -r requirements.txt`
- `startCommand`: `python app.py --host 0.0.0.0 --port $PORT`
- `healthCheckPath`: `/healthz`
- `autoDeployTrigger`: `commit`

Observacao importante:
- O arquivo `render.yaml` nao fixa o plano.
- Se sua conta tiver opcao de plano gratis e voce quiser usar esse plano, confira isso antes de finalizar no painel.
- Se o Render criar como `starter`, isso depende das opcoes disponiveis na sua conta.

## Opcao 2: Preenchimento manual no painel do Render

Se preferir criar sem Blueprint, preencha exatamente assim:

- `New`: `Web Service`
- `Repository`: selecione este repositorio
- `Branch`: `main`
- `Runtime` / `Language`: `Python 3`
- `Region`: `Oregon`
- `Build Command`: `pip install -r requirements.txt`
- `Start Command`: `python app.py --host 0.0.0.0 --port $PORT`
- `Health Check Path`: `/healthz`
- `Auto-Deploy`: `Yes`

### Environment Variables

Nenhuma variavel obrigatoria precisa ser criada manualmente.

O Render ja fornece:
- `PORT`

E este projeto ja inclui:
- `.python-version` com `3.12`

Se o painel do Render pedir versao de Python manualmente, mantenha a linha `3.12` do arquivo `.python-version` como referencia.

## O que o app faz no Render

- abre a interface web
- recebe o PDF enviado pelo usuario
- recebe os codigos digitados por virgula
- filtra as linhas da tabela
- gera e devolve o Excel em download

## Endpoints uteis

- pagina principal: `/`
- health check: `/healthz`

## Validacao antes de subir

Confira se estes arquivos estao no GitHub:
- `app.py`
- `autuacao_extractor.py`
- `web/index.html`
- `render.yaml`
- `requirements.txt`
- `.python-version`

## Observacoes

- O app nao usa banco de dados.
- O app nao exige armazenamento persistente.
- O processamento do PDF acontece em memoria.
- O arquivo enviado nao precisa ser salvo em disco para gerar o resultado.
