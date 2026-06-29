"""
processing.py — Handlers de eventos do M6.

denuncia.encaminhada → SEMPRE notifica o cidadão (fechamento do ciclo).
denuncia.priorizada  → APENAS para CRITICO e ALTO, alerta a secretaria.

Idempotência: INSERT ... ON CONFLICT DO NOTHING em (denuncia_id, tipo).
Processar o mesmo evento duas vezes não gera duplicata no banco.
"""
from __future__ import annotations

import logging

from pydantic import ValidationError

from .cliente_secretaria import buscar_contato
from .config import get_settings
from .db import AsyncSessionLocal
from .notificador import alertar_secretaria, notificar_cidadao
from .schemas import DenunciaEncaminhada, DenunciaPriorizada

logger = logging.getLogger("m6.processing")


async def handle_encaminhada(corpo: bytes) -> None:
    try:
        ev = DenunciaEncaminhada.model_validate_json(corpo)
    except ValidationError as e:
        logger.error("denuncia.encaminhada inválida: %s", e)
        raise

    async with AsyncSessionLocal() as session:
        await notificar_cidadao(
            session,
            denuncia_id=ev.id,
            secretaria_nome=ev.secretaria_nome,
            nivel=ev.nivel,
            categoria=ev.categoria or "geral",
            area_responsavel=ev.area_responsavel,
            score=ev.score,
        )
    logger.info("Cidadão notificado: denúncia=%s -> %s", ev.id, ev.secretaria_sigla)


async def handle_priorizada(corpo: bytes) -> None:
    try:
        ev = DenunciaPriorizada.model_validate_json(corpo)
    except ValidationError as e:
        logger.error("denuncia.priorizada inválida: %s", e)
        raise

    cfg = get_settings()
    if ev.nivel not in cfg.niveis_alerta:
        logger.debug(
            "Nivel %s fora dos limiares de alerta (%s) — ignorando id=%s",
            ev.nivel, cfg.niveis_alerta, ev.id,
        )
        return

    secretaria = await buscar_contato(ev.area_responsavel)

    async with AsyncSessionLocal() as session:
        await alertar_secretaria(
            session,
            denuncia_id=ev.id,
            nivel=ev.nivel,
            categoria=ev.categoria or "geral",
            area_responsavel=ev.area_responsavel,
            score=ev.score,
            secretaria=secretaria,
        )
    logger.info(
        "Secretaria alertada: denúncia=%s nivel=%s -> %s",
        ev.id, ev.nivel, secretaria["email"],
    )


HANDLERS = {
    "denuncia.encaminhada": handle_encaminhada,
    "denuncia.priorizada":  handle_priorizada,
}


async def dispatcher(routing_key: str, corpo: bytes) -> None:
    handler = HANDLERS.get(routing_key)
    if handler:
        await handler(corpo)
    else:
        logger.debug("Routing key ignorada pelo M6: %s", routing_key)
