from app.agents.retraction_checker import classify


def test_retraction_notice_detected():
    status, notices = classify([
        {
            "type": "retraction",
            "DOI": "10.1/n",
            "source": "retraction-watch",
        }
    ])

    assert status == "retracted"
    assert notices[0]["doi"] == "10.1/n"


def test_concern_and_correction():
    assert classify([
        {"type": "expression_of_concern"}
    ])[0] == "concern"

    assert classify([
        {"type": "correction"}
    ])[0] == "clear"


def test_retraction_beats_concern():
    assert classify([
        {"type": "retraction"},
        {"type": "expression_of_concern"},
    ])[0] == "retracted"