"""
messaging.py — Transporte RabbitMQ do M6.

Topologia:
    exchange `denuncias` (topic, durável)
      └─ fila `m6.notificacoes`
            ├─ bind: denuncia.encaminhada  ← M5
            └─ bind: denuncia.priorizada   ← M3 (apenas CRITICO/ALTO processados)

O M6 usa dois bindings na mesma fila — padrão normal em RabbitMQ topic exchange.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from .config import Settings

logger = logging.getLogger("m6.messaging")

Dispatcher = Callable[[str, bytes], Awaitable[None]]

BINDING_KEYS = ["denuncia.encaminhada", "denuncia.priorizada"]


class Mensageria:
    def __init__(self, cfg: Settings):
        self.cfg = cfg
        self._conn: aio_pika.RobustConnection | None = None
        self._canal: aio_pika.abc.AbstractRobustChannel | None = None
        self._fila: aio_pika.abc.AbstractQueue | None = None

    async def conectar(self) -> None:
        self._conn = await aio_pika.connect_robust(self.cfg.rabbitmq_url)
        self._canal = await self._conn.channel()
        await self._canal.set_qos(prefetch_count=self.cfg.prefetch)

        exchange = await self._canal.declare_exchange(
            self.cfg.exchange, aio_pika.ExchangeType.TOPIC, durable=True
        )

        dlx_nome = f"{self.cfg.exchange}.dlx"
        dlq_nome = f"{self.cfg.fila}.dlq"
        dlx = await self._canal.declare_exchange(
            dlx_nome, aio_pika.ExchangeType.TOPIC, durable=True
        )
        dlq = await self._canal.declare_queue(dlq_nome, durable=True)
        await dlq.bind(dlx, routing_key="#")

        self._fila = await self._canal.declare_queue(
            self.cfg.fila,
            durable=True,
            arguments={"x-dead-letter-exchange": dlx_nome},
        )
        for key in BINDING_KEYS:
            await self._fila.bind(exchange, routing_key=key)

        logger.info(
            "Mensageria pronta: fila=%s | bindings=%s",
            self.cfg.fila, BINDING_KEYS,
        )

    async def consumir(self, dispatcher: Dispatcher) -> None:
        assert self._fila is not None

        async def _on_message(message: AbstractIncomingMessage) -> None:
            async with message.process(requeue=False):
                await dispatcher(message.routing_key or "", message.body)

        await self._fila.consume(_on_message)

    async def fechar(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            logger.info("Conexão com o RabbitMQ fechada.")

    @property
    def conectado(self) -> bool:
        return self._conn is not None and not self._conn.is_closed
