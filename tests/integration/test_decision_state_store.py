from __future__ import annotations

from tradar.schemas import DecisionState
from tradar.state.decisions import DecisionStateStore


def test_decision_state_store_upserts_by_card_id(tmp_path) -> None:
    store = DecisionStateStore(tmp_path / "state.sqlite")
    store.initialize()

    first = store.save(DecisionState(card_id="card_demo", decision="accept", note="Start it."))
    second = store.save(DecisionState(card_id="card_demo", decision="reject", note="Changed mind."))

    loaded = store.get("card_demo")

    assert first.card_id == second.card_id
    assert loaded is not None
    assert loaded.decision == "reject"
    assert loaded.note == "Changed mind."
    assert [state.card_id for state in store.list_all()] == ["card_demo"]
