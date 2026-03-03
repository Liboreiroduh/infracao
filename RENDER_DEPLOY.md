# Deploy no Render Free

Este projeto foi ajustado para subir no Render sem Blueprint.

Use o fluxo manual de `Web Service`.

Arquivos importantes para o deploy:
- `app.py`
- `autuacao_extractor.py`
- `web/index.html`
- `requirements.txt`
- `.python-version`

## O que preencher no Render

Crie um servico em:
- `New` > `Web Service`

Preencha assim:
- `Repository`: selecione este repositorio
- `Branch`: `main`
- `Root Directory`: deixe vazio
- `Name`: `filtro-autuacoes-pdf`
- `Runtime`: `Python 3`
- `Region`: escolha a regiao que preferir
- `Branch Auto-Deploy`: `Yes`
- `Build Command`: `pip install -r requirements.txt`
- `Start Command`: `python app.py`
- `Health Check Path`: `/healthz`

Se o painel mostrar escolha de plano/instance:
- selecione a opcao gratuita disponivel na sua conta

## Variaveis de ambiente

Nao precisa criar nenhuma variavel manualmente.

O app ja funciona assim:
- o Render fornece `PORT`
- o `app.py` detecta esse `PORT`
- o `app.py` muda automaticamente para `0.0.0.0` quando estiver em ambiente hospedado

Se o Render pedir versao do Python manualmente:
- use `3.12`

## O que NAO preencher

Nao precisa adicionar:
- banco de dados
- disco persistente
- Redis
- variaveis customizadas
- Blueprint

## Como o app funciona no Render

- abre a interface web
- recebe o PDF enviado pelo usuario
- recebe os codigos separados por virgula
- processa o PDF em memoria
- devolve o arquivo `.xlsx` para download

## Endpoints uteis

- pagina principal: `/`
- health check: `/healthz`

## Checklist antes de subir para o GitHub

Confirme que estes arquivos estao no repositorio:
- `app.py`
- `autuacao_extractor.py`
- `web/index.html`
- `requirements.txt`
- `.python-version`
- `RENDER_DEPLOY.md`

## Observacoes importantes

- O app nao usa banco.
- O app nao precisa salvar arquivos no servidor para funcionar.
- O processamento acontece em memoria.
- O deploy foi preparado para o fluxo manual do Render Free.
