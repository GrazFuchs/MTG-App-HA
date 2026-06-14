"""Sprint 24 (item 5): triage duplicate-check correctness.

A new copy that merges into an existing collection row (same printing +
condition + language) must still recognise the PRE-EXISTING copy in that row as
a duplicate, instead of reporting "no other printings owned".
"""
from _helpers import add_acquisition_event, add_collection, insert_card
from app.database import get_db
from app.services.triage_advisor import get_suggestion


async def test_detects_duplicate_in_merged_row():
    db = await get_db()
    cid = await insert_card(db, "Sol Ring", type_line="Artifact",
                            color_identity=[], price_eur="2.00")
    # One row holding 2 copies: 1 pre-existing + 1 just-arrived (merged in).
    col_id = await add_collection(db, cid, quantity=2)
    ev_id = await add_acquisition_event(db, cid, qty_delta=1)
    event_row = {"id": ev_id, "card_id": cid, "collection_id": col_id,
                 "is_foil": False, "qty_delta": 1}

    suggestion, printings, _ = await get_suggestion(db, event_row)
    # The leftover copy in the same row is a genuine duplicate.
    assert len(printings) == 1
    assert printings[0].quantity == 1
    assert suggestion.action in ("swap", "sold_new")


async def test_new_only_copy_is_not_a_duplicate():
    db = await get_db()
    cid = await insert_card(db, "Lonely Card", type_line="Instant",
                            color_identity=["R"], price_eur="1.00")
    col_id = await add_collection(db, cid, quantity=1)  # only the new copy
    ev_id = await add_acquisition_event(db, cid, qty_delta=1)
    event_row = {"id": ev_id, "card_id": cid, "collection_id": col_id,
                 "is_foil": False, "qty_delta": 1}

    suggestion, printings, _ = await get_suggestion(db, event_row)
    assert printings == []
    assert suggestion.action == "keep"


async def test_other_printing_detected_as_duplicate():
    db = await get_db()
    # Same card name, two different printings (separate collection rows).
    old = await insert_card(db, "Counterspell", type_line="Instant",
                            color_identity=["U"], set_code="3ed", price_eur="3.00")
    new = await insert_card(db, "Counterspell", type_line="Instant",
                            color_identity=["U"], set_code="mh2", price_eur="1.00")
    await add_collection(db, old, quantity=1)
    new_col = await add_collection(db, new, quantity=1)
    ev_id = await add_acquisition_event(db, new, qty_delta=1)
    event_row = {"id": ev_id, "card_id": new, "collection_id": new_col,
                 "is_foil": False, "qty_delta": 1}

    suggestion, printings, _ = await get_suggestion(db, event_row)
    # The other (older, pricier) printing is detected as the duplicate. The new
    # copy is the cheaper one, so the advice is to sell the new copy.
    assert {p.set_code for p in printings} == {"3ed"}
    assert suggestion.action == "sold_new"
