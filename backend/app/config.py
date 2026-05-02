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
    sync_enabled: bool = True
    sync_hour: int = 3
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
