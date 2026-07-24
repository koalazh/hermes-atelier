from __future__ import annotations

import json
from typing import Any

RECORDS = (
    {
        "record_id": "PRD-LOGIN-17",
        "terms": ("login", "sign in", "登录", "验证码"),
        "owner": "Identity Experience",
        "known_behavior": "SMS codes can arrive late on congested carriers.",
        "release_note": "The resend timer was reduced in simulated release 1.4.2.",
    },
    {
        "record_id": "PRD-EXPORT-08",
        "terms": ("export", "download", "导出", "下载"),
        "owner": "Workspace Data",
        "known_behavior": "Large exports are prepared asynchronously.",
        "release_note": "Progress text was clarified in simulated release 1.5.0.",
    },
)

SCHEMA = {
    "name": "voc_product_lookup",
    "description": "Search deterministic simulated product evidence by feature or symptom.",
    "parameters": {
        "type": "object",
        "properties": {"query": {"type": "string", "minLength": 1}},
        "required": ["query"],
        "additionalProperties": False,
    },
}


def register(ctx: Any) -> None:
    def lookup(args: dict[str, Any], **_: Any) -> str:
        query = str(args.get("query", "")).casefold()
        matches = [
            record
            for record in RECORDS
            if any(term.casefold() in query for term in record["terms"])
        ]
        return json.dumps({"simulated": True, "matches": matches}, ensure_ascii=False)

    ctx.register_tool(
        name="voc_product_lookup",
        toolset="mini-voc-product",
        schema=SCHEMA,
        handler=lookup,
        description="Simulated Mini VOC product lookup",
        emoji="📦",
    )
