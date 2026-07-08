"""Tests for the token counting helper in test/_lib/token_counter.py.

These tests verify the tiktoken-based counting utilities work correctly
before we integrate them into the broader test suite.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make _lib importable from test/scenarios/agent-mode/.
_TEST_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(_TEST_ROOT))

from _lib.token_counter import count_tokens, count_tokens_in_messages


# --------------------------------------------------------------------------- #
# count_tokens
# --------------------------------------------------------------------------- #

def test_count_tokens_for_known_string():
    """Verify encoding against a known input/output pair.

    "Hello world" encodes to 2 tokens in cl100k_base (GPT-4o default).
    """
    result = count_tokens("Hello world")
    assert result == 2, f"Expected 2 tokens for 'Hello world', got {result}"


def test_count_tokens_for_longer_string():
    """A longer string should produce a proportional token count."""
    text = "The quick brown fox jumps over the lazy dog"
    result = count_tokens(text)
    # This string is 9 words, typically 9-11 tokens in cl100k_base.
    assert 7 <= result <= 12, f"Expected 7-12 tokens, got {result}"


def test_count_tokens_with_model_override():
    """Passing an explicit model should work independently of env var."""
    text = "Hello world"
    result = count_tokens(text, model="gpt-4o")
    assert result == 2


def test_count_tokens_handles_empty_input():
    """Empty string should return 0 tokens."""
    assert count_tokens("") == 0


def test_count_tokens_handles_whitespace_only():
    """Whitespace-only input should still produce a small count."""
    result = count_tokens("   ")
    assert result >= 1, "Whitespace should tokenize to at least 1 token"


# --------------------------------------------------------------------------- #
# count_tokens_in_messages
# --------------------------------------------------------------------------- #

def test_count_tokens_in_messages_includes_all_roles():
    """Messages with different roles should all contribute to the count."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    result = count_tokens_in_messages(messages)
    # Each message: ~4 tokens overhead + content tokens.
    # system: 4 + "You are a helpful assistant." (~7) = ~11
    # user: 4 + "Hello" (~1) = ~5
    # assistant: 4 + "Hi there!" (~3) = ~7
    # Reply priming: 3
    # Total: ~26
    assert result > 20, f"Expected >20 tokens for 3 messages, got {result}"


def test_count_tokens_in_messages_single_message():
    """A single message should still include overhead."""
    messages = [{"role": "user", "content": "Hello world"}]
    result = count_tokens_in_messages(messages)
    # 2 content tokens + 4 message overhead + 3 reply priming = 9
    assert result >= 8, f"Expected >=8 tokens, got {result}"


def test_count_tokens_in_messages_empty_list():
    """Empty message list should return 0."""
    assert count_tokens_in_messages([]) == 0


def test_count_tokens_in_messages_model_override():
    """Explicit model parameter should work."""
    messages = [{"role": "user", "content": "Test"}]
    result = count_tokens_in_messages(messages, model="gpt-4o")
    assert result > 0


def test_count_tokens_in_messages_non_string_values():
    """Non-string values in message dict should be skipped gracefully."""
    messages = [{"role": "user", "content": "Hello", "name": "test_user"}]
    result = count_tokens_in_messages(messages)
    # "name" value "test_user" is a string, so it should be counted too.
    assert result > 5
