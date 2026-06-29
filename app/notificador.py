"""
notificador.py — Lógica de envio simulado de notificações.

Em produção, este módulo seria substituído por integrações reais:
  - E-mail: SendGrid / AWS SES / SMTP
  - SMS: Twilio / AWS SNS
  - Push: Firebase Cloud Messaging
  - Webhook: POST no sistema da secretaria

Para o contexto de demonstração do projeto, as notificações são
registradas no log e gravadas no banco (PostgreSQL), evidenciando
que o ciclo foi fechado sem depender de credenciais externas.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Notificacao

logger = logging.getLogger("m6.notificador")


async def notificar_cidadao(
    session: AsyncSession,
    *,
    denuncia_id: str,
    secretaria_nome: str,
    nivel: str,
    categoria: str,
    area_responsavel: str,
    score: float,
) -> None:
    """Avisa o cidadão que sua denúncia foi encaminhada à secretaria competente."""
    mensagem = (
        f"Sua denúncia sobre '{categoria}' foi encaminhada para {secretaria_nome}. "
        f"Prioridade: {nivel} (score {score:.1f}). "
        "Acompanhe o andamento pelo Conecta Recife."
    )
    destinatario = f"cidadao+{denuncia_id[:8]}@conectarecife.recife.pe.gov.br"

    logger.info(
        "[CIDADÃO] encaminhada → %s | denúncia=%s | secretaria=%s | nivel=%s",
        destinatario, denuncia_id, secretaria_nome, nivel,
    )

    conteudo = json.dumps(
        {
            "mensagem": mensagem,
            "denuncia_id": denuncia_id,
            "secretaria": secretaria_nome,
            "nivel": nivel,
            "categoria": categoria,
        },
        ensure_ascii=False,
    )

    stmt = (
        pg_insert(Notificacao)
        .values(
            denuncia_id=denuncia_id,
            tipo="CIDADAO_ENCAMINHADA",
            destinatario=destinatario,
            canal="LOG",
            conteudo=conteudo,
            evento_origem="denuncia.encaminhada",
            status="ENVIADA",
        )
        .on_conflict_do_nothing(index_elements=["denuncia_id", "tipo"])
    )
    await session.execute(stmt)
    await session.commit()


async def alertar_secretaria(
    session: AsyncSession,
    *,
    denuncia_id: str,
    nivel: str,
    categoria: str,
    area_responsavel: str,
    score: float,
    secretaria: dict,
) -> None:
    """Alerta a secretaria sobre denúncia de alta criticidade."""
    tipo = f"SECRETARIA_ALERTA_{nivel}"
    destinatario = secretaria["email"]

    urgencia = "URGENTE" if nivel == "CRITICO" else "PRIORITÁRIO"
    mensagem = (
        f"[{urgencia}] Denúncia #{denuncia_id[:8]} de '{categoria}' "
        f"atingiu nível {nivel} (score {score:.1f}). "
        f"Área: {area_responsavel}. Ação imediata necessária."
    )

    logger.warning(
        "[SECRETARIA → %s (%s)] %s | denúncia=%s",
        destinatario, secretaria.get("sigla", ""), mensagem, denuncia_id,
    )

    conteudo = json.dumps(
        {
            "mensagem": mensagem,
            "denuncia_id": denuncia_id,
            "nivel": nivel,
            "score": score,
            "categoria": categoria,
            "area_responsavel": area_responsavel,
            "secretaria_nome": secretaria.get("nome", ""),
            "secretaria_email": destinatario,
        },
        ensure_ascii=False,
    )

    stmt = (
        pg_insert(Notificacao)
        .values(
            denuncia_id=denuncia_id,
            tipo=tipo,
            destinatario=destinatario,
            canal="LOG",
            conteudo=conteudo,
            evento_origem="denuncia.priorizada",
            status="ENVIADA",
        )
        .on_conflict_do_nothing(index_elements=["denuncia_id", "tipo"])
    )
    await session.execute(stmt)
    await session.commit()
