"""Lightweight token counting utilities for test assertions.

Uses tiktoken to measure token consumption in LLM agent outputs.
Default encoding is cl100k_base (GPT-4o / GPT-4-turbo / GPT-3.5-turbo).

Override the model via env var CV_PILOT_TOKEN_MODEL (e.g. "gpt-4", "gpt-3.5-turbo").
"""

from __future__ import annotations

import os

import tiktoken

_DEFAULT_MODEL = "gpt-4o"

# Cache the encoding object to avoid repeated lookups.
_encoding: tiktoken.Encoding | None = None


def _get_encoding() -> tiktoken.Encoding:
    """Return the tiktoken encoding for the configured model."""
    global _encoding
    if _encoding is None:
        model = os.environ.get("CV_PILOT_TOKEN_MODEL", _DEFAULT_MODEL)
        _encoding = tiktoken.encoding_for_model(model)
    return _encoding


def count_tokens(text: str, model: str | None = None) -> int:
    """Count tokens in a plain string.

    Parameters
    ----------
    text:
        The text to tokenize.
    model:
        Override the model encoding for this call only.
        If None, uses the module-level default (env var or gpt-4o).
    """
    if not text:
        return 0
    if model is not None:
        enc = tiktoken.encoding_for_model(model)
    else:
        enc = _get_encoding()
    return len(enc.encode(text))


def count_tokens_in_messages(messages: list[dict], model: str | None = None) -> int:
    """Count tokens in a chat-format messages list.

    Follows OpenAI's token accounting for chat completions:
    - Each message has a role overhead (~4 tokens per message).
    - The total has a fixed overhead of ~3 tokens for the reply priming.

    Parameters
    ----------
    messages:
        List of dicts with at least "role" and "content" keys.
    model:
        Override the model encoding for this call only.
    """
    if not messages:
        return 0
    if model is not None:
        enc = tiktoken.encoding_for_model(model)
    else:
        enc = _get_encoding()

    # Per-message overhead: <|start|>{role}\n ... <|end|> = ~4 tokens each.
    tokens_per_message = 4
    # Reply priming overhead.
    tokens_reply = 3

    total = tokens_reply
    for msg in messages:
        total += tokens_per_message
        for value in msg.values():
            if isinstance(value, str):
                total += len(enc.encode(value))
    return total
