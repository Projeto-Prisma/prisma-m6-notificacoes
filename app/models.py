"""
models.py — Modelo ORM do banco de notificações (M6).

Uma linha por notificação enviada (ou tentada). O par (denuncia_id, tipo)
tem restrição UNIQUE para garantir idempotência: o mesmo evento processado
duas vezes não gera duas notificações ao mesmo destinatário.

Tipos de notificação:
  CIDADAO_ENCAMINHADA    — avisa o cidadão que sua denúncia foi encaminhada
  SECRETARIA_ALERTA_CRITICO — alerta a secretaria de denúncia crítica
  SECRETARIA_ALERTA_ALTO    — alerta a secretaria de denúncia de prioridade alta
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Notificacao(Base):
    __tablename__ = "notificacoes"
    __table_args__ = (
        UniqueConstraint("denuncia_id", "tipo", name="uq_denuncia_tipo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    denuncia_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(64), nullable=False)
    destinatario: Mapped[str] = mapped_column(String(256), nullable=False)
    canal: Mapped[str] = mapped_column(String(32), nullable=False, default="LOG")
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)
    evento_origem: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ENVIADA")
    lida: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
