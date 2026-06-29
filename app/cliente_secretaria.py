"""
cliente_secretaria.py — Consulta o M9 para obter o e-mail/contato da secretaria.

M6 usa esse dado para incluir no log do alerta. Se o M9 estiver offline
ou não retornar resultado, M6 usa um endereço genérico e segue em frente —
a notificação NÃO é bloqueada por indisponibilidade do M9.
"""
from __future__ import annotations

import logging

import httpx

from .config import get_settings

logger = logging.getLogger("m6.cliente_secretaria")

_FALLBACK_EMAIL = "secretarias@recife.pe.gov.br"


async def buscar_contato(area: str, secretaria_sigla: str | None = None) -> dict:
    """
    Retorna dict com pelo menos {"email": str, "nome": str}.
    Nunca lança exceção — em caso de falha retorna dados genéricos.
    """
    cfg = get_settings()
    params = {"area": area}
    if secretaria_sigla:
        params["sigla"] = secretaria_sigla

    try:
        async with httpx.AsyncClient(timeout=cfg.secretarias_timeout_s) as client:
            resp = await client.get(f"{cfg.secretarias_api_url}/secretarias", params=params)
            if resp.status_code == 200:
                data = resp.json()
                secretaria = data[0] if isinstance(data, list) and data else data
                if secretaria and isinstance(secretaria, dict):
                    return {
                        "nome": secretaria.get("nome", area),
                        "sigla": secretaria.get("sigla", secretaria_sigla or ""),
                        "email": secretaria.get("email_notificacoes", _FALLBACK_EMAIL),
                    }
    except Exception as exc:
        logger.debug("M9 indisponível para area=%s: %s", area, exc)

    return {"nome": area, "sigla": secretaria_sigla or "", "email": _FALLBACK_EMAIL}
