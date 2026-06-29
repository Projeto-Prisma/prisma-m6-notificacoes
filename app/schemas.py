"""
schemas.py — Contratos Pydantic do M6.

Eventos consumidos:
  denuncia.encaminhada ← M5 (Java, snake_case)
  denuncia.priorizada  ← M3 (Python)

Schemas da API HTTP:
  NotificacaoResponse, ContagemItem
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# denuncia.encaminhada  (M5 — Java)
# ---------------------------------------------------------------------------
class DenunciaEncaminhada(BaseModel):
    id: str
    secretaria_id: str | None = None
    secretaria_nome: str
    secretaria_sigla: str
    nivel: str
    categoria: str | None = None
    area_responsavel: str
    score: float
    encaminhada_em: Any = None  # pode chegar como string do Java


# ---------------------------------------------------------------------------
# denuncia.priorizada  (M3 — Python)
# ---------------------------------------------------------------------------
class DenunciaPriorizada(BaseModel):
    id: str
    score: float = Field(ge=0, le=100)
    nivel: str
    categoria: str | None = None
    area_responsavel: str
    urgencia_categoria: float
    peso_confianca: float
    boost_recorrencia: float
    priorizado_em: datetime


# ---------------------------------------------------------------------------
# API — resposta de notificação
# ---------------------------------------------------------------------------
class NotificacaoResponse(BaseModel):
    id: int
    denuncia_id: str
    tipo: str
    destinatario: str
    canal: str
    conteudo: str
    evento_origem: str
    status: str
    lida: bool = False
    criado_em: datetime

    model_config = {"from_attributes": True}


class ContagemItem(BaseModel):
    chave: str
    total: int
