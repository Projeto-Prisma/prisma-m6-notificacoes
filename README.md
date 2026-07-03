# M6 — Notificações

## Responsabilidade

Fechar o ciclo de comunicação de uma denúncia: avisar o cidadão quando ela é encaminhada à secretaria responsável e alertar internamente a secretaria quando a denúncia atinge um nível de prioridade alto ou crítico.

O M6 é **consumidor puro** de eventos — não publica nada de volta no exchange `denuncias`. Cada notificação processada fica registrada em banco, servindo de histórico e alimentando a tela de Notificações do painel (M8).

> Os canais de envio (e-mail, SMS, push, webhook) são **simulados** nesta versão: o disparo é registrado em log e persistido no banco, sem depender de credenciais externas. O código já isola essa responsabilidade em `app/notificador.py`, pronto para plugar um provedor real (SendGrid/SES, Twilio/SNS, Firebase Cloud Messaging, POST de webhook) sem alterar o restante do fluxo.

---

## Posição na Arquitetura

```
                    exchange "denuncias" (topic, durável)
                              │
        ┌─────────────────────┼─────────────────────┐
        │ denuncia.encaminhada│ denuncia.priorizada  │
        │ (publicado pelo M5) │ (publicado pelo M3)  │
        ▼                     ▼                      
  ┌──────────────────────────────────┐
  │      fila  m6.notificacoes       │   dois bindings, uma fila só
  │           (durável)              │
  └──────────────────────────────────┘
                │
                ▼
        ┌───────────────┐        REST         ┌──────────────┐
        │  M6 — worker   │ ───────────────────▶│  M9 (contatos)│
        │  + API HTTP    │◀────fallback se     └──────────────┘
        └───────────────┘      M9 indisponível
                │
                ▼
        tabela `notificacoes` (PostgreSQL)
                │
                ▼
        GET /notificacoes, /alertas, /estatisticas → consumido pelo M8
```

- **Consome:** `denuncia.encaminhada` (M5) e `denuncia.priorizada` (M3, apenas níveis `CRITICO`/`ALTO`)
- **Publica:** nenhum evento
- **Consulta via REST:** M9, para obter o contato de alerta da secretaria
- **É consultado via REST por:** M8 (painel), para exibir o histórico de notificações

---

## Stack

| Componente     | Tecnologia |
|----------------|-----------|
| API            | Python 3.12 · FastAPI |
| Mensageria     | RabbitMQ · `aio-pika` (cliente AMQP assíncrono) |
| Banco          | PostgreSQL · SQLAlchemy 2.0 assíncrono (`asyncpg`) |
| Cliente REST   | `httpx` (assíncrono, para consultar o M9) |
| Container      | Docker |

---

## RabbitMQ — Mensageria

Arquivo: `app/messaging.py`

| Item | Valor |
|------|-------|
| Exchange | `denuncias` (topic, durável) |
| Fila | `m6.notificacoes` (durável) |
| Bindings | `denuncia.encaminhada`, `denuncia.priorizada` |
| Dead Letter Exchange | `denuncias.dlx` |
| Dead Letter Queue | `m6.notificacoes.dlq` (bind `#`) |
| Prefetch | 10 mensagens por vez (configurável) |
| Confirmação | manual, via `message.process(requeue=False)` após o processamento |
| Reconexão | `aio_pika.connect_robust()` — reconecta automaticamente se o broker cair |

Uma única fila recebe dois bindings diferentes — não é necessário criar uma fila por tipo de evento quando o mesmo consumidor trata ambos.

**Idempotência:** como o RabbitMQ garante entrega *at-least-once*, o mesmo evento pode, em cenários de falha, ser entregue mais de uma vez. Para evitar notificação duplicada, a tabela `notificacoes` tem uma `UNIQUE CONSTRAINT` em `(denuncia_id, tipo)` e a gravação usa `INSERT ... ON CONFLICT DO NOTHING` (`app/notificador.py`). Reprocessar o mesmo evento não gera duplicata.

**Roteamento de eventos** (`app/processing.py`): um dicionário (`HANDLERS`) mapeia `routing_key → função` — `denuncia.encaminhada` sempre notifica o cidadão; `denuncia.priorizada` só gera alerta para a secretaria quando o nível está entre os configurados em `niveis_alerta` (por padrão, `CRITICO` e `ALTO`).

---

## Banco de Dados

**Nome:** `notificacoes` · **Driver:** `postgresql+asyncpg`

```sql
CREATE TABLE notificacoes (
    id            SERIAL PRIMARY KEY,
    denuncia_id   VARCHAR(64)  NOT NULL,
    tipo          VARCHAR(64)  NOT NULL,   -- CIDADAO_ENCAMINHADA | SECRETARIA_ALERTA_CRITICO | SECRETARIA_ALERTA_ALTO
    destinatario  VARCHAR(256) NOT NULL,
    canal         VARCHAR(32)  NOT NULL DEFAULT 'LOG',
    conteudo      TEXT         NOT NULL,   -- JSON com os detalhes da notificação
    evento_origem VARCHAR(64)  NOT NULL,   -- routing key que originou o registro
    status        VARCHAR(32)  NOT NULL DEFAULT 'ENVIADA',
    lida          BOOLEAN      NOT NULL DEFAULT FALSE,
    criado_em     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (denuncia_id, tipo)
);
CREATE INDEX ON notificacoes (denuncia_id);
```

A tabela é criada via `Base.metadata.create_all()` no startup da aplicação (`app/db.py`) — não há migrations com Alembic neste módulo.

---

## Endpoints da API

| Método  | Rota | Descrição |
|---------|------|-----------|
| `GET`   | `/health` | Status da aplicação e da conexão com o broker |
| `GET`   | `/notificacoes` | Lista notificações (filtros: `tipo`, `denuncia_id`, `limite`, `offset`) |
| `GET`   | `/notificacoes/{denuncia_id}` | Todas as notificações de uma denúncia específica |
| `PATCH` | `/notificacoes/{id}/lida` | Marca uma notificação como lida |
| `PATCH` | `/notificacoes/marcar-todas-lidas` | Marca todas as notificações como lidas |
| `GET`   | `/alertas` | Lista apenas notificações do tipo `SECRETARIA_ALERTA_*` |
| `GET`   | `/estatisticas` | Total de notificações e contagem agrupada por tipo |

---

## Como executar

### Subir junto com o sistema completo

```bash
# na raiz do projeto prisma-infra
docker compose up --build
```

A API do M6 fica disponível em `http://localhost:8006`.

> Este módulo não tem `.env` próprio: suas variáveis são injetadas pelo `docker-compose.yml` da raiz do projeto.

---

## Variáveis de ambiente

Todas usam o prefixo `M6_` (`app/config.py`, via `pydantic-settings`):

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `M6_DATABASE_URL` | Conexão com o PostgreSQL (assíncrona) | `postgresql+asyncpg://prisma:prisma_secret@db-m6:5432/notificacoes` |
| `M6_RABBITMQ_URL` | Conexão AMQP com o RabbitMQ | `amqp://guest:guest@rabbitmq:5672/` |
| `M6_EXCHANGE` | Nome do exchange consumido | `denuncias` |
| `M6_FILA` | Nome da fila do M6 | `m6.notificacoes` |
| `M6_PREFETCH` | Mensagens entregues por vez ao worker | `10` |
| `M6_SECRETARIAS_API_URL` | Base URL do M9, para buscar contatos | `http://m9-secretarias:8000` |
| `M6_SECRETARIAS_TIMEOUT_S` | Timeout da chamada REST ao M9 | `3.0` |
| `M6_NIVEIS_ALERTA` | Níveis de prioridade que disparam alerta à secretaria | `["CRITICO", "ALTO"]` |

A porta HTTP interna é fixa em `8000` (definida no `Dockerfile`), mapeada externamente para `8006`.

---

## Relação com outros módulos

| Módulo | Relação |
|--------|---------|
| M3 — Priorização | Publica `denuncia.priorizada`, consumida pelo M6 para decidir alertas |
| M5 — Roteamento | Publica `denuncia.encaminhada`, consumida pelo M6 para notificar o cidadão |
| M9 — Secretarias | Consultado via REST para obter o e-mail de alerta da secretaria (com timeout e fallback caso indisponível) |
| M8 — Painel Web | Consome a API HTTP do M6 (`/notificacoes`, `/alertas`, `/estatisticas`) para exibir o feed de notificações |

---

## Testes

Ainda não há testes automatizados neste módulo.

---

## Contexto do projeto

O sistema completo é composto por 9 módulos que tratam denúncias cidadãs do Conecta Recife de forma automatizada e distribuída, comunicando-se majoritariamente por eventos no RabbitMQ (exchange `denuncias`, tipo topic). O M6 é o módulo responsável por transformar esses eventos em avisos concretos para cidadãos e gestores.
