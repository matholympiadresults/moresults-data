"""Tests for data_processing/sources/IMO/ingester/imo_ingester.py."""

from data_processing.sources.imo.ingester.imo_ingester import sanitize_name


class TestSanitizeName:
    """Tests for sanitize_name function which handles '? ' prefix from IMO source."""

    def test_removes_question_mark_prefix(self):
        assert sanitize_name("? LastName") == "LastName"

    def test_leaves_normal_names_unchanged(self):
        assert sanitize_name("First Last") == "First Last"

    def test_leaves_question_mark_without_space(self):
        # Only "? " pattern should be removed, not just "?"
        assert sanitize_name("?Name") == "?Name"

    def test_leaves_question_mark_in_middle(self):
        assert sanitize_name("First ? Last") == "First ? Last"

    def test_handles_empty_string(self):
        assert sanitize_name("") == ""
