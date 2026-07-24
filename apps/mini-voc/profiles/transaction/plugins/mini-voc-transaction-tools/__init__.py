from __future__ import annotations

import json
from typing import Any

RECORDS = {
    "ORD-1001": {"status": "refunded", "event_time": "2026-07-20T09:30:00Z"},
    "ORD-1002": {"status": "payment_pending", "event_time": "2026-07-23T14:10:00Z"},
}

SCHEMA = {
    "name": "voc_transaction_lookup",
    "description": "Retrieve one deterministic simulated transaction by exact order ID.",
    "parameters": {
        "type": "object",
        "properties": {"order_id": {"type": "string", "minLength": 1}},
        "required": ["order_id"],
        "additionalProperties": False,
    },
}


def register(ctx: Any) -> None:
    def lookup(args: dict[str, Any], **_: Any) -> str:
        order_id = str(args.get("order_id", "")).upper()
        if order_id == "ORD-FAIL":
            raise RuntimeError("simulated transaction provider unavailable")
        record = RECORDS.get(order_id)
        return json.dumps(
            {"simulated": True, "order_id": order_id, "record": record},
            ensure_ascii=False,
        )

    ctx.register_tool(
        name="voc_transaction_lookup",
        toolset="mini-voc-transaction",
        schema=SCHEMA,
        handler=lookup,
        description="Simulated Mini VOC transaction lookup",
        emoji="🧾",
    )
