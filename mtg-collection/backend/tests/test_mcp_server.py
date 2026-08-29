"""The MCP surface: what it exposes, and that its prompts do not lie.

A prompt is instructions for an assistant that cannot check them. If it names a
tool that does not exist, the assistant discovers this mid-task and improvises —
which is worse than not having the prompt, because the improvisation looks like
the intended behaviour. That happened while writing Sprint 11: the rewritten
`analyze_deck` told the assistant to call `set_deck_gameplan` and
`set_deck_user_bracket`, and neither existed.
"""
import asyncio
import inspect
import re

import pytest

from app import mcp_server


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture(scope="module")
def tool_names():
    return {t.name for t in asyncio.run(mcp_server.mcp.list_tools())}


def test_prompts_only_reference_tools_that_exist(tool_names):
    src = inspect.getsource(mcp_server)
    prompts_src = src[src.index("# --- Prompts ---"):]

    # Backticked snake_case words in a prompt are tool names by convention.
    # Field names appear the same way, so they are listed as known exceptions
    # rather than guessed at — a heuristic that silently skips things would
    # defeat the point of the test.
    field_names = {"ai_assessment_updated_at", "updated_at", "owned_only"}
    referenced = {
        n for n in re.findall(r"`([a-z_]{4,})`", prompts_src)
        if "_" in n and n not in field_names
    }
    assert referenced, "no tools referenced — the extraction stopped working"
    missing = sorted(referenced - tool_names)
    assert missing == [], f"prompts name tools that do not exist: {missing}"


def test_the_write_tools_the_analyze_prompt_relies_on_are_present(tool_names):
    """The point of Sprint 11's prompt rewrite: the analysis gets *recorded*.

    Measured 2026-08-29: 4 of 22 decks had an assessment at all, and every one
    of the four predated its deck's last edit. The old prompt only asked for an
    analysis, so the answer stayed in the chat window.
    """
    for name in ("set_deck_ai_assessment", "set_deck_gameplan", "set_deck_user_bracket"):
        assert name in tool_names


def test_destructive_tools_require_explicit_confirmation(tool_names):
    """`clear_cardmarket_listings` deletes every listing and cannot be undone.

    An assistant asked to "tidy up" would otherwise wipe the lot on one
    sentence — the prices, conditions and the link back to the triage decision
    that created each listing are not recoverable from Cardmarket.
    """
    tools = {t.name: t for t in asyncio.run(mcp_server.mcp.list_tools())}
    schema = tools["clear_cardmarket_listings"].inputSchema
    assert "confirm" in schema.get("properties", {})


def test_triage_decisions_go_through_the_shared_service():
    """One booking path for REST and MCP.

    They were two, and the MCP one wrote no `decision_snapshot`, kept no notes
    and never told the HA publisher — so a card decided through Claude left no
    trace in the archive and the sensors stayed stale. Neither call site was
    wrong on its own, which is exactly why it went unnoticed.
    """
    src = inspect.getsource(mcp_server.decide_triage)
    assert "apply_decision" in src
    assert "INSERT INTO cardmarket_listings" not in src, (
        "the MCP tool has its own booking logic again")


def test_every_suggestion_call_site_passes_the_event_id():
    """Sibling awareness is opt-in by accident.

    `get_suggestion` only counts the other pending events for the same card
    when the caller puts `id` in the event dict — and it uses `.get("id")`, so
    leaving it out is not an error, it just silently returns a different
    recommendation. The MCP tool was the one call site of four that did, which
    meant an assistant looking at a bulk import advised something other than
    what the web UI displayed for the same card.

    Checked by reading the source rather than by calling: the failure is a
    missing key, and a runtime test would have to construct the exact overlap
    of pending events that makes the two answers differ.
    """
    import app.routers.acquisitions as rest
    import app.services.ha_metrics as metrics

    for module in (mcp_server, rest, metrics):
        src = inspect.getsource(module)
        for block in re.findall(r"event_row = \{(.*?)\}", src, re.S):
            if "card_id" not in block:
                continue
            assert '"id"' in block, (
                f"{module.__name__}: event_row without an id — the suggestion "
                f"will not see sibling events")
