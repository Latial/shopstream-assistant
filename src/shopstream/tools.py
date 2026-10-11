from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from shopstream.retrieval import Retriever, hits_to_search_results

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "search_knowledge_base",
        "description": (
            "Search ShopStream's product catalogue, policies and FAQ. Use this for "
            "any question about products, shipping, returns, warranty or company "
            "policy. Prefer a specific query over a vague one; you may call this "
            "more than once with different phrasings if the first result set does "
            "not contain the answer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to look for, phrased as a search query.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_order",
        "description": (
            "Look up one order by its id. Returns customer, product, status and the "
            "order and delivery dates. Use it whenever the user refers to a specific "
            "order, and before answering any question whose answer depends on when "
            "an order was delivered."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string",
                             "description": "The order id, e.g. '1042'."}
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "draft_refund",
        "description": (
            "Create a DRAFT refund for human approval. This does not move any money "
            "and does not notify the customer. Only call it after you have checked "
            "the order with get_order and confirmed eligibility against the returns "
            "policy with search_knowledge_base. State the policy basis in `reason`."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "amount_eur": {"type": "number",
                               "description": "Refund amount in EUR."},
                "reason": {"type": "string",
                           "description": "Why this refund is justified, citing the "
                                          "policy that permits it."},
            },
            "required": ["order_id", "amount_eur", "reason"],
        },
    },
]

class ToolBox:
    """Executes tool calls. Every handler returns the `content` for a tool_result."""

    def __init__(self, retriever: Retriever, db: sqlite3.Connection):
        self.retriever = retriever
        self.db = db
        self.last_hits: list = [] # kept so tracking can record what was retrived 

    def run(self, name : str, args: dict) -> Any:
        if name == "search_knowledge_base":
            return self._search(args["query"])
        if name == "get_order":
            return self._get_order(args["order_id"])
        if name == "draft_refund":
            return self._draft_refund(args["order_id"], float(args["amount_eur"]), args["reason"])
        return f"Unknown tool : {name}"

    #handlers
    def _search(self, query :str) -> list[dict] | str:
        hits = self.retriever.search(query)
        self.last_hits.extend(hits)
        if not hits:
            return "No results were found in the knowledge base for that query"
        return hits_to_search_results(hits)

    def _get_order(self, order_id: str) -> str:
        row = self.db.execute(
            "SELECT * FROM orders where order_id = ?", (order_id.strip(),)).fetchone()
        if row is None:
            return f"No order found with id {order_id!r}."
        return(
            f"order_id: {row['order_id']}\ncustomer: {row['customer']}\n"
            f"product: {row['product_name']} ({row['sku']})\n"
            f"quantity: {row['quantity']}\ntotal_eur: {row['total_eur']}\n"
            f"status: {row['status']}\nordered_at: {row['ordered_at']}\n"
            f"delivered_at: {row['delivered_at'] or 'not yet delivered'}"
        )

    def _draft_refund(self, order_id: str, amount_eur: float, reason:str) -> str:
        row = self.db.execute(
            "SELECT total_eur FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if row is None:
            return f"Cannot draft a refund: no order {order_id!r}."
        if amount_eur <= 0 or amount_eur > float(row["total_eur"]):
            return (f"Refused: amount €{amount_eur:.2f} is outside the valid range "
                 f"(0, €{row['total_eur']:.2f}] for order {order_id}.")
        with self.db:
            cur = self.db.execute(
                "INSERT INTO refund_drafts (order_id, amount_eur, reason, status, created_at) VALUES (?, ?, ?, 'pending_human_approval', ?)", (order_id, amount_eur, reason, datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )
            return (f"Draft refund #{cur.lastrowid} created for order {order_id}: "
                    f"€{amount_eur:.2f} status pending_human_approval. "
                    f"No money has moved and the customer has not been notified."
                    )