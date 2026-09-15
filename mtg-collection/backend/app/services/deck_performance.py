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
            "matches": 0, "match_wins": 0, "match_losses": 0,
            "match_win_rate": 0.0,
            "sideboard_games": 0, "game_2_3_win_rate": 0.0,
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
        **_match_stats(games),
    }


def _match_stats(games: list[dict[str, Any]]) -> dict[str, Any]:
    """Matches, and how the games after sideboarding went.

    **A match is the group of its games and its winner is computed, never
    stored.** Whoever won more games won the match; equal is a draw, which is
    what an abandoned 1-1 actually was. A stored result could disagree with the
    games it came from, and then there would be two answers.

    **An ungrouped game counts as a match of one.** In a best-of-three format a
    lone game *is* a Bo1 match, and leaving those out would quietly drop most
    of the table. Where nothing is grouped, `match_win_rate` equals `win_rate` —
    which is the truth, not a bug.

    `game_2_3_win_rate` is the one number only best-of-three can produce and the
    reason the sideboard notes are worth writing: a deck that keeps winning
    game one and losing the match has a sideboard problem, not a deck problem.
    """
    groups: dict[Any, list[dict[str, Any]]] = {}
    for index, game in enumerate(games):
        # An ungrouped game is its own match. The index keeps two of them from
        # colliding under a shared `None` key.
        key = game.get("match_id") or ("single", index)
        groups.setdefault(key, []).append(game)

    match_wins = match_losses = 0
    for members in groups.values():
        wins = sum(1 for g in members if g["result"] == "win")
        losses = sum(1 for g in members if g["result"] == "loss")
        if wins > losses:
            match_wins += 1
        elif losses > wins:
            match_losses += 1

    # Everything from game two on: played against an opponent who has seen the
    # deck and changed fifteen cards in response.
    after_board = [g for g in games if (g.get("game_in_match") or 1) >= 2]
    board_wins = sum(1 for g in after_board if g["result"] == "win")

    return {
        "matches": len(groups),
        "match_wins": match_wins,
        "match_losses": match_losses,
        "match_win_rate": round(match_wins / len(groups) * 100, 1) if groups else 0.0,
        "sideboard_games": len(after_board),
        "game_2_3_win_rate": (
            round(board_wins / len(after_board) * 100, 1) if after_board else 0.0
        ),
    }
