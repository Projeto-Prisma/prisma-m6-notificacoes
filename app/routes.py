from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import func, select, text, update

from .db import AsyncSessionLocal
from .models import Notificacao
from .schemas import ContagemItem, NotificacaoResponse

router = APIRouter()


@router.get("/health", tags=["infra"])
async def health(request: Request):
    mensageria = getattr(request.app.state, "mensageria", None)
    return {
        "status": "ok",
        "broker_conectado": mensageria.conectado if mensageria else False,
    }


# ---------------------------------------------------------------------------
# Log de notificações
# ---------------------------------------------------------------------------

@router.get("/notificacoes", response_model=list[NotificacaoResponse], tags=["notificacoes"])
async def listar(
    limite: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    tipo: str | None = Query(None),
    denuncia_id: str | None = Query(None),
):
    async with AsyncSessionLocal() as session:
        q = select(Notificacao).order_by(Notificacao.criado_em.desc())
        if tipo:
            q = q.where(Notificacao.tipo.ilike(f"%{tipo}%"))
        if denuncia_id:
            q = q.where(Notificacao.denuncia_id == denuncia_id)
        q = q.offset(offset).limit(limite)
        resultado = await session.execute(q)
        return resultado.scalars().all()


@router.patch("/notificacoes/marcar-todas-lidas", tags=["notificacoes"])
async def marcar_todas_lidas():
    async with AsyncSessionLocal() as session:
        await session.execute(update(Notificacao).values(lida=True))
        await session.commit()
    return {"ok": True}


@router.patch("/notificacoes/{id}/lida", tags=["notificacoes"])
async def marcar_lida(id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            update(Notificacao).where(Notificacao.id == id).values(lida=True)
        )
        await session.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Notificação não encontrada")
    return {"ok": True}


@router.get("/notificacoes/{denuncia_id}", response_model=list[NotificacaoResponse], tags=["notificacoes"])
async def por_denuncia(denuncia_id: str):
    async with AsyncSessionLocal() as session:
        resultado = await session.execute(
            select(Notificacao)
            .where(Notificacao.denuncia_id == denuncia_id)
            .order_by(Notificacao.criado_em)
        )
        return resultado.scalars().all()


# ---------------------------------------------------------------------------
# Alertas enviados às secretarias
# ---------------------------------------------------------------------------

@router.get("/alertas", response_model=list[NotificacaoResponse], tags=["notificacoes"])
async def alertas(
    limite: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Retorna notificações do tipo SECRETARIA_ALERTA_* em ordem decrescente."""
    async with AsyncSessionLocal() as session:
        resultado = await session.execute(
            select(Notificacao)
            .where(Notificacao.tipo.like("SECRETARIA_ALERTA%"))
            .order_by(Notificacao.criado_em.desc())
            .offset(offset)
            .limit(limite)
        )
        return resultado.scalars().all()


# ---------------------------------------------------------------------------
# Estatísticas
# ---------------------------------------------------------------------------

@router.get("/estatisticas", tags=["notificacoes"])
async def estatisticas():
    async with AsyncSessionLocal() as session:
        total = (await session.execute(select(func.count()).select_from(Notificacao))).scalar()
        por_tipo_rows = await session.execute(
            select(Notificacao.tipo, func.count().label("total"))
            .group_by(Notificacao.tipo)
            .order_by(text("total DESC"))
        )
        por_tipo = [{"chave": row.tipo, "total": row.total} for row in por_tipo_rows]
        return {"total_notificacoes": total, "por_tipo": por_tipo}
