"""Deck performance aggregation (pure functions — easy to unit-test)."""
from typing import Any


def compute_performance_stats(games: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate a list of game rows into summary statistics.

    `games` are expected to be ordered newest-first (by played_at DESC, id DESC),
    matching the list endpoint, so games[0] is the most recent game.
    """
    total = len(games)
    if total == 0:
        return {
            "games": 0, "wins": 0, "losses": 0, "draws": 0, "win_rate": 0.0,
            "on_play_games": 0, "on_play_wins": 0, "on_play_win_rate": 0.0,
            "avg_mulligans": 0.0, "avg_missed_land_drops": 0.0, "avg_turns": 0.0,
            "last_played_at": None, "last_result": None,
        }

    wins = sum(1 for g in games if g["result"] == "win")
    losses = sum(1 for g in games if g["result"] == "loss")
    draws = sum(1 for g in games if g["result"] == "draw")

    on_play = [g for g in games if g.get("on_play")]
    on_play_wins = sum(1 for g in on_play if g["result"] == "win")

    def _avg(key: str) -> float:
        return round(sum(g.get(key, 0) or 0 for g in games) / total, 2)

    return {
        "games": total,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": round(wins / total * 100, 1),
        "on_play_games": len(on_play),
        "on_play_wins": on_play_wins,
        "on_play_win_rate": round(on_play_wins / len(on_play) * 100, 1) if on_play else 0.0,
        "avg_mulligans": _avg("mulligans"),
        "avg_missed_land_drops": _avg("missed_land_drops"),
        "avg_turns": _avg("turns"),
        "last_played_at": games[0]["played_at"],
        "last_result": games[0]["result"],
    }
