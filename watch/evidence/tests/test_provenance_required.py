from review.provenance_gate import check_source_authorized


def test_rejects_unauthorized_source():
    result = check_source_authorized({"authorization_status": "unverified_do_not_use"})
    assert result["authorized"] is False


def test_accepts_owned_source():
    result = check_source_authorized({"authorization_status": "authorized_owned"})
    assert result["authorized"] is True
