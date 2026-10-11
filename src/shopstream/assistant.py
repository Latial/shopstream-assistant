"""The tool loop. No framework — this is the whole agent, and it fits on a page."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any

import anthropic

from shopstream.config import PROMPTS_DIR, Settings
from shopstream.tools import TOOL_SCHEMAS, ToolBox


MAX_TOTAL_ROUNDS = 6

@dataclass
class Citation:
    clited_text: str
    source: str
    title: str | None

@dataclass
class Answer:
    text: str = ""
    citations: list[Citation] = field(default_factory=list)
    tool_calls : list[str] = field(default_factory=list)
    retrieved_chunk_ids: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    rounds: int = 0
    latency_s: float = 0.0

class Assistant:
    def __init__(self, settings: Settings, toolbox: ToolBox):
        self.s = settings
        self.toolbox = toolbox
        self.client = anthropic.Anthropic(api_key=settings.anthropic_key)
        self.system = (PROMPTS_DIR / "system.md").read_text(encoding="utf-8")

    def ask(self, question: str, history: list[dict] | None = None) -> Answer:
        messages: list[dict[str, Any]] = list(history or [])
        messages.append({"role": "user", "content" : question})

        answer = Answer()
        self.toolbox.last_hits = []
        start = time.monotonic()

        for _ in range(MAX_TOTAL_ROUNDS):
            answer.rounds += 1
            response = self.client.messages.create(
                model=self.s.answer_model,
                max_tokens=1500,
                system=[{
                    "type" : "text",
                    "text": self.system,
                    #the system promp is indentical on every call so best to cache it.
                    "cache_control": {"type" : "ephemeral"},
                }],
                tools=TOOL_SCHEMAS,
                messages=messages,
            )
            u = response.usage
            answer.input_tokens += u.input_tokens
            answer.output_tokens += u.output_tokens
            answer.cache_read_tokens += getattr(u, "cache_read_input_tokens", 0) or 0
            answer.cache_write_tokens += getattr(u, "cache_creation_input_tokens", 0 ) or 0

            if(response.stop_reason != "tool_use"):
                self._collect_text(response, answer)
                break

            # Run every tool the model asked for, then hand the results back.

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                answer.tool_calls.append(block.name)
                result = self.toolbox.run(block.name, block.input)
                tool_results.append({
                    "type" : "tool_result",
                    "tool_use_id" : block.id,
                    "content" : result,
                })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            answer.text = ("I could not complete that within the allowed number of "
                           "steps. Please rephrase or ask a support agent.")

        answer.retrieved_chunk_ids = [h.chunk_id for h in self.toolbox.last_hits]
        answer.latency_s = round(time.monotonic() - start,2)
        return answer

    @staticmethod
    def _collect_text(response, answer: Answer) -> None:
        for block in response.content:
            if block.type != "text":
                continue
            answer.text += block.text
            for c in getattr(block, "citations", None) or []:
                answer.citations.append(Citation(
                    cited_text=getattr(c, "cited_text", ""),
                    source=getattr(c, "source", ""),
                    title=getattr(c,"title", None),
                ))