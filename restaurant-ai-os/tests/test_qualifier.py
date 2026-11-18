from slai.agents.qualifier import QualifierAgent

def test_parking_question_does_not_invent_booking_details():
    state = QualifierAgent().extract(
        "Здравствуйте, подскажите, пожалуйста, есть ли парковка?"
    )

    assert state.party_size == 0
    assert state.date == ""
    assert state.time == ""
    assert state.missing_fields == ["party_size", "date", "time"]

def test_extracts_russian_party_word_with_explicit_group_context():
    state = QualifierAgent().extract(
        "Нас будет четверо, дату и время уточню позже."
    )

    assert state.party_size == 4
    assert state.date == ""
    assert state.time == ""
    assert state.missing_fields == ["date", "time"]

def test_keeps_existing_numeric_booking_extraction():
    state = QualifierAgent().extract(
        "Стол на 4 человека 2030-01-01 в 19:00"
    )

    assert state.party_size == 4
    assert state.date == "2030-01-01"
    assert state.time == "19:00"
    assert state.missing_fields == []
