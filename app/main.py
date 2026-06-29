"""
main.py — Ciclo de vida do M6 (Notificações).

Startup:
  1. Cria tabela `notificacoes` no PostgreSQL (idempotente).
  2. Conecta ao RabbitMQ e registra dois bindings:
       denuncia.encaminhada — notifica o cidadão
       denuncia.priorizada  — alerta a secretaria (CRITICO/ALTO)
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import criar_tabelas
from .messaging import Mensageria
from .processing import dispatcher
from .routes import router

cfg = get_settings()
logging.basicConfig(
    level=cfg.log_level,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger("m6")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await criar_tabelas()

    mensageria = Mensageria(cfg)
    app.state.mensageria = mensageria
    await mensageria.conectar()
    await mensageria.consumir(dispatcher)
    logger.info(
        "M6 no ar — consumindo denuncia.encaminhada e denuncia.priorizada."
    )

    yield

    await mensageria.fechar()
    logger.info("M6 finalizado.")


app = FastAPI(title=cfg.app_nome, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/", tags=["infra"])
async def raiz():
    return {
        "modulo": cfg.app_nome,
        "docs": "/docs",
        "endpoints": [
            "/health",
            "/notificacoes",
            "/notificacoes/{denuncia_id}",
            "/alertas",
            "/estatisticas",
        ],
    }
