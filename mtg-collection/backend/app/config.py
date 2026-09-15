"""Configuration loaded from HA add-on options."""
import json
import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    archidekt_username: str = ""
    archidekt_password: str = ""
    archidekt_user_id: int = 0
    archidekt_deck_ids: list[int] = []
    #: Archidekt folders whose decks do not tie up the cards they list — a
    #: disassembled deck's cards are on the shelf, and an older version of a
    #: deck holds the same cards as the one that replaced it. Counting both is
    #: what made 268 cards read as "needed more often than owned".
    #: A deck can be told otherwise individually; see `decks.binds_copies`.
    non_binding_folders: list[str] = ["Disassembled", "Older Versions"]
    #: Archidekt folders whose decks never raise a legality notification. A
    #: deck that is being built is not *illegal* — the question does not apply
    #: to it yet, which is the house rule "not applicable means NULL plus a
    #: reason, never a number". Two of the three findings on the first full
    #: check were 43-card and 2-card drafts, and a checker that pushes on every
    #: change to a 2-card draft gets switched off rather than fixed.
    #: A deck can be told otherwise individually; see `decks.legality_push`.
    no_legality_push_folders: list[str] = ["Work in Progress"]
    sync_enabled: bool = True
    sync_hour: int = 3
    mtgstocks_enabled: bool = False
    mcp_auth_token: str = ""
    cardmarket_username: str = ""
    mqtt_enabled: bool = False
    mqtt_host: str = ""
    mqtt_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""
    mqtt_topic_prefix: str = "mtg-collection"
    notify_min_alert_value_eur: float = 5.0
    notify_webhook_url: str = ""
    notify_via_ha_service: str = ""
    data_dir: str = "/data"
    db_path: str = "/data/mtg.db"
    ingress_entry: str = "/"

    model_config = {"env_prefix": "", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    options_path = os.environ.get("OPTIONS_PATH", "/data/options.json")
    data_dir = os.environ.get("DATA_DIR", "/data")
    ingress_entry = os.environ.get("INGRESS_ENTRY", "/")

    kwargs: dict = {
        "data_dir": data_dir,
        "db_path": os.path.join(data_dir, "mtg.db"),
        "ingress_entry": ingress_entry,
    }

    if Path(options_path).exists():
        with open(options_path) as f:
            opts = json.load(f)
        kwargs.update(opts)

    return Settings(**kwargs)
