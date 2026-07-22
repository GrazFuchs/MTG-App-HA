"""Sprint 31: the HA game-logger form (MQTT input entities)."""
import json

import pytest
from _helpers import insert_deck
from app.database import get_db
from app.services import ha_form, ha_publisher
from app.services.ha_entities import discovery_payload, discovery_topic
from conftest import FakeMqttClient

PREFIX = "mtg-collection"


# --- entities ---------------------------------------------------------------


def test_form_entity_components():
    entities = {e.key: e for e in ha_form.form_entities(PREFIX, ["—", "Atraxa"])}

    assert entities["log_deck"].component == "select"
    assert entities["log_pod_size"].component == "number"
    assert entities["log_on_play"].component == "switch"
    assert entities["log_opponents"].component == "text"
    assert entities["log_submit"].component == "button"
    assert entities["log_status"].component == "sensor"


def test_form_entity_ids():
    entities = {e.key: e for e in ha_form.form_entities(PREFIX, [])}
    assert entities["log_deck"].object_id == "mtg_log_deck"
    assert entities["log_submit"].object_id == "mtg_log_submit"


def test_deck_select_carries_the_options():
    entities = {e.key: e for e in ha_form.form_entities(PREFIX, ["—", "Atraxa", "Krenko"])}
    payload = discovery_payload(entities["log_deck"], PREFIX, f"{PREFIX}/status")

    assert payload["options"] == ["—", "Atraxa", "Krenko"]
    assert payload["command_topic"] == "mtg-collection/form/deck/set"
    assert payload["state_topic"] == "mtg-collection/form/deck"


def test_number_bounds_reach_the_discovery_payload():
    entities = {e.key: e for e in ha_form.form_entities(PREFIX, [])}
    payload = discovery_payload(entities["log_pod_size"], PREFIX, f"{PREFIX}/status")

    assert (payload["min"], payload["max"]) == (1, 8)
    assert payload["mode"] == "box"


def test_button_has_no_state_topic():
    """HA rejects a button discovery config that carries a state_topic."""
    entities = {e.key: e for e in ha_form.form_entities(PREFIX, [])}
    payload = discovery_payload(entities["log_submit"], PREFIX, f"{PREFIX}/status")

    assert "state_topic" not in payload
    assert payload["command_topic"] == "mtg-collection/form/submit/set"
    assert payload["payload_press"] == "PRESS"
    assert discovery_topic(entities["log_submit"]).startswith("homeassistant/button/")


def test_text_fields_are_capped_at_the_ha_limit():
    entities = {e.key: e for e in ha_form.form_entities(PREFIX, [])}
    payload = discovery_payload(entities["log_notes"], PREFIX, f"{PREFIX}/status")
    assert payload["max"] == ha_form.TEXT_MAX == 255


def test_form_bounds_match_the_game_model():
    """A form that allows a value the API rejects would fail only on submit."""
    ha_form.validate_bounds()


# --- deck options -----------------------------------------------------------


@pytest.mark.anyio
async def test_deck_options_start_with_the_empty_marker():
    db = await get_db()
    deck_id = await insert_deck(db, "Atraxa")

    labels, mapping = await ha_form.deck_options(db)

    assert labels == [ha_form.NO_DECK, "Atraxa"]
    assert mapping == {"Atraxa": deck_id}


@pytest.mark.anyio
async def test_duplicate_deck_names_get_disambiguated():
    db = await get_db()
    first = await insert_deck(db, "Krenko")
    second = await insert_deck(db, "Krenko")

    labels, mapping = await ha_form.deck_options(db)

    assert labels == [ha_form.NO_DECK, f"Krenko (#{first})", f"Krenko (#{second})"]
    assert mapping[f"Krenko (#{second})"] == second


# --- field commands ---------------------------------------------------------


@pytest.mark.anyio
async def test_numbers_are_clamped_to_their_bounds():
    db = await get_db()
    assert await ha_form.set_field(db, "pod_size", "99") == "8"
    assert await ha_form.set_field(db, "pod_size", "0") == "1"
    # HA sends numbers as floats
    assert await ha_form.set_field(db, "turns", "12.0") == "12"


@pytest.mark.anyio
async def test_invalid_number_is_rejected():
    db = await get_db()
    with pytest.raises(ValueError):
        await ha_form.set_field(db, "turns", "many")


@pytest.mark.anyio
async def test_switch_payloads():
    db = await get_db()
    assert await ha_form.set_field(db, "on_play", "ON") == "ON"
    assert await ha_form.set_field(db, "on_play", "OFF") == "OFF"
    assert await ha_form.set_field(db, "on_play", "true") == "ON"


@pytest.mark.anyio
async def test_select_rejects_unknown_options():
    db = await get_db()
    with pytest.raises(ValueError):
        await ha_form.set_field(db, "result", "victory")

    await insert_deck(db, "Atraxa")
    with pytest.raises(ValueError):
        await ha_form.set_field(db, "deck", "Yuriko")
    assert await ha_form.set_field(db, "deck", "Atraxa") == "Atraxa"


@pytest.mark.anyio
async def test_long_text_is_truncated_not_rejected():
    db = await get_db()
    stored = await ha_form.set_field(db, "notes", "x" * 400)
    assert len(stored) == ha_form.TEXT_MAX


@pytest.mark.anyio
async def test_unknown_field_is_rejected():
    db = await get_db()
    with pytest.raises(ValueError):
        await ha_form.set_field(db, "nonsense", "1")


@pytest.mark.anyio
async def test_state_survives_a_restart():
    """Values live in the DB, not in memory."""
    db = await get_db()
    await insert_deck(db, "Atraxa")
    await ha_form.set_field(db, "deck", "Atraxa")
    await ha_form.set_field(db, "turns", "7")

    values = await ha_form.load_state(db)
    assert values["deck"] == "Atraxa"
    assert values["turns"] == "7"
    # Untouched fields fall back to their defaults
    assert values["result"] == "win"
    assert values["pod_size"] == "4"


# --- submit -----------------------------------------------------------------


@pytest.mark.anyio
async def test_submit_writes_the_game_and_resets():
    db = await get_db()
    deck_id = await insert_deck(db, "Atraxa")
    await ha_form.set_field(db, "deck", "Atraxa")
    await ha_form.set_field(db, "result", "loss")
    await ha_form.set_field(db, "turns", "11")
    await ha_form.set_field(db, "on_play", "ON")
    await ha_form.set_field(db, "notes", "flooded")

    result = await ha_form.submit(db)

    assert result["status"] == "logged"
    cursor = await db.execute("SELECT * FROM deck_games WHERE id = ?", (result["game_id"],))
    row = await cursor.fetchone()
    assert row["deck_id"] == deck_id
    assert row["result"] == "loss"
    assert row["turns"] == 11
    assert row["on_play"] == 1
    assert row["notes"] == "flooded"

    # Form is empty again
    values = await ha_form.load_state(db)
    assert values["deck"] == ha_form.NO_DECK
    assert values["turns"] == "0"
    assert values["notes"] == ""


@pytest.mark.anyio
async def test_submit_without_a_deck_is_an_error():
    db = await get_db()
    result = await ha_form.submit(db)

    assert result["error"] == "No deck selected"
    cursor = await db.execute("SELECT COUNT(*) FROM deck_games")
    assert (await cursor.fetchone())[0] == 0


@pytest.mark.anyio
async def test_submit_after_the_deck_disappeared():
    """A deck deleted while it sat selected must not silently log elsewhere."""
    db = await get_db()
    deck_id = await insert_deck(db, "Atraxa")
    await ha_form.set_field(db, "deck", "Atraxa")

    await db.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
    await db.commit()

    result = await ha_form.submit(db)

    assert "no longer exists" in result["error"]
    cursor = await db.execute("SELECT COUNT(*) FROM deck_games")
    assert (await cursor.fetchone())[0] == 0


def test_status_text():
    assert ha_form.status_text({"error": "boom"}) == "Error: boom"
    assert ha_form.status_text({
        "result": "win", "deck_name": "Atraxa", "played_at": "2026-07-22",
    }) == "Logged win with Atraxa on 2026-07-22"
    assert len(ha_form.status_text({"error": "x" * 400})) == 255


# --- MQTT round trip --------------------------------------------------------


@pytest.mark.anyio
async def test_form_command_echoes_the_new_state(fake_mqtt):
    db = await get_db()
    await insert_deck(db, "Atraxa")

    await ha_publisher._on_form_message("mtg-collection/form/turns/set", b"9")

    published = [(t, p) for t, p, _ in FakeMqttClient.all_published()]
    assert ("mtg-collection/form/turns", "9") in published
    assert (await ha_form.load_state(db))["turns"] == "9"


@pytest.mark.anyio
async def test_rejected_command_keeps_the_old_state(fake_mqtt):
    db = await get_db()
    await ha_form.set_field(db, "turns", "5")

    await ha_publisher._on_form_message("mtg-collection/form/turns/set", b"nonsense")

    topics = [t for t, _, _ in FakeMqttClient.all_published()]
    assert "mtg-collection/form/turns" not in topics  # old value left alone
    assert "mtg-collection/form/status" in topics
    assert (await ha_form.load_state(db))["turns"] == "5"


@pytest.mark.anyio
async def test_button_press_logs_and_resets(fake_mqtt):
    db = await get_db()
    await insert_deck(db, "Atraxa")
    await ha_form.set_field(db, "deck", "Atraxa")
    await ha_form.set_field(db, "result", "win")

    await ha_publisher._on_form_message("mtg-collection/form/submit/set", b"PRESS")

    published = dict((t, p) for t, p, _ in FakeMqttClient.all_published())
    assert published["mtg-collection/form/status"].startswith("Logged win with Atraxa")
    # The reset values are pushed back to HA
    assert published["mtg-collection/form/deck"] == ha_form.NO_DECK

    cursor = await db.execute("SELECT COUNT(*) FROM deck_games")
    assert (await cursor.fetchone())[0] == 1


@pytest.mark.anyio
async def test_failed_submit_reports_on_the_status_sensor(fake_mqtt):
    await ha_publisher._on_form_message("mtg-collection/form/submit/set", b"PRESS")

    published = dict((t, p) for t, p, _ in FakeMqttClient.all_published())
    assert published["mtg-collection/form/status"] == "Error: No deck selected"
    assert "mtg-collection/form/deck" not in published  # nothing reset


@pytest.mark.anyio
async def test_publish_form_resets_a_deck_that_vanished(fake_mqtt):
    db = await get_db()
    deck_id = await insert_deck(db, "Atraxa")
    await ha_form.set_field(db, "deck", "Atraxa")
    await db.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
    await db.commit()

    await ha_publisher.publish_form_entities()

    published = dict((t, p) for t, p, _ in FakeMqttClient.all_published())
    # HA refuses a select state outside its options, so it goes back to the marker
    assert published["mtg-collection/form/deck"] == ha_form.NO_DECK
    config = json.loads(published["homeassistant/select/mtg_collection_log_deck/config"])
    assert config["options"] == [ha_form.NO_DECK]


@pytest.mark.anyio
async def test_publish_form_sends_every_entity(fake_mqtt):
    await insert_deck(await get_db(), "Atraxa")

    await ha_publisher.publish_form_entities()

    configs = [t for t, _, _ in FakeMqttClient.all_published() if t.startswith("homeassistant/")]
    assert len(configs) == len(ha_form.FIELDS) + 2  # + submit button + status sensor
    assert "homeassistant/button/mtg_collection_log_submit/config" in configs


