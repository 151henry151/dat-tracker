"""Tests for Jon King–style show.txt rendering."""

from dat_tracker.show_txt import format_show_txt


def test_format_show_txt_matches_jon_template_shape():
    text = format_show_txt(
        artist="John Cowan Band",
        date="2002-08-02",
        venue="Riverbend Music Center",
        city="Cincinnati",
        state="OH",
        source="SBD > DAT",
        transfer="DAT > Sony PCM-2600>ESI U24XL > Audacity > FLAC",
        transferer="Cate Crowe",
        tracker="dat-tracker",
        set_label="One Set",
        tracks=[
            {"num": 1, "title": "My Heart Will Follow You >"},
            {"num": 2, "title": "Banter"},
        ],
    )
    assert text.startswith("John Cowan Band\n")
    assert "August 2, 2002 (2002-08-02)" in text
    assert "Riverbend Music Center" in text
    assert "Cincinnati, OH" in text
    assert "Source: SBD > DAT" in text
    assert "Transferred by: Cate Crowe" in text
    assert "Tracked & Uploaded by: dat-tracker" in text
    assert "One Set:" in text
    assert "1. My Heart Will Follow You >" in text
    assert "2. Banter" in text
