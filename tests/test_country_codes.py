"""Tests for data_processing/country_codes.py."""

import pytest
from pydantic import BaseModel, ValidationError

from data_processing.country_codes import (
    COUNTRY_NAMES,
    VALID_ISO_CODES,
    ISOCountryCode,
    get_country_name,
)


class TestCountryNames:
    def test_country_names_is_dict(self):
        assert isinstance(COUNTRY_NAMES, dict)

    def test_has_common_countries(self):
        assert "usa" in COUNTRY_NAMES
        assert "gbr" in COUNTRY_NAMES
        assert "chn" in COUNTRY_NAMES
        assert "deu" in COUNTRY_NAMES
        assert "fra" in COUNTRY_NAMES
        assert "jpn" in COUNTRY_NAMES

    def test_country_names_values_are_strings(self):
        for code, name in COUNTRY_NAMES.items():
            assert isinstance(code, str), f"Code {code} should be string"
            assert isinstance(name, str), f"Name {name} should be string"

    def test_all_codes_are_lowercase(self):
        for code in COUNTRY_NAMES:
            assert code == code.lower(), f"Code {code} should be lowercase"

    def test_has_historical_countries(self):
        assert "uss" in COUNTRY_NAMES  # Soviet Union
        assert "yug" in COUNTRY_NAMES  # Yugoslavia
        assert "gdr" in COUNTRY_NAMES  # East Germany
        assert "csk" in COUNTRY_NAMES  # Czechoslovakia

    def test_has_special_codes(self):
        assert "unknown" in COUNTRY_NAMES

    def test_country_name_content(self):
        assert COUNTRY_NAMES["usa"] == "United States"
        assert COUNTRY_NAMES["gbr"] == "United Kingdom"
        assert COUNTRY_NAMES["deu"] == "Germany"
        assert COUNTRY_NAMES["uss"] == "Soviet Union"


class TestValidIsoCodes:
    def test_is_frozenset(self):
        assert isinstance(VALID_ISO_CODES, frozenset)

    def test_matches_country_names_keys(self):
        assert VALID_ISO_CODES == frozenset(COUNTRY_NAMES.keys())

    def test_contains_common_codes(self):
        assert "usa" in VALID_ISO_CODES
        assert "gbr" in VALID_ISO_CODES
        assert "chn" in VALID_ISO_CODES

    def test_does_not_contain_invalid_codes(self):
        assert "xxx" not in VALID_ISO_CODES
        assert "abc" not in VALID_ISO_CODES
        assert "" not in VALID_ISO_CODES


class TestGetCountryName:
    def test_returns_correct_name(self):
        assert get_country_name("usa") == "United States"
        assert get_country_name("gbr") == "United Kingdom"
        assert get_country_name("deu") == "Germany"

    def test_case_insensitive(self):
        assert get_country_name("USA") == "United States"
        assert get_country_name("Gbr") == "United Kingdom"
        assert get_country_name("DEU") == "Germany"

    def test_raises_for_invalid_code(self):
        with pytest.raises(KeyError):
            get_country_name("xxx")

    def test_historical_countries(self):
        assert get_country_name("uss") == "Soviet Union"
        assert get_country_name("yug") == "Yugoslavia"


class TestISOCountryCode:
    """Tests for the Pydantic validated type alias."""

    def test_valid_code_in_model(self):
        class TestModel(BaseModel):
            code: ISOCountryCode

        model = TestModel(code="usa")
        assert model.code == "usa"

    def test_invalid_code_raises_validation_error(self):
        class TestModel(BaseModel):
            code: ISOCountryCode

        with pytest.raises(ValidationError) as exc_info:
            TestModel(code="xxx")

        assert "Invalid ISO country code" in str(exc_info.value)

    def test_empty_code_raises_validation_error(self):
        class TestModel(BaseModel):
            code: ISOCountryCode

        with pytest.raises(ValidationError):
            TestModel(code="")

    def test_valid_historical_code(self):
        class TestModel(BaseModel):
            code: ISOCountryCode

        model = TestModel(code="uss")
        assert model.code == "uss"

    def test_multiple_valid_codes(self):
        class TestModel(BaseModel):
            codes: list[ISOCountryCode]

        model = TestModel(codes=["usa", "gbr", "deu", "fra"])
        assert model.codes == ["usa", "gbr", "deu", "fra"]

    def test_mixed_valid_invalid_codes(self):
        class TestModel(BaseModel):
            codes: list[ISOCountryCode]

        with pytest.raises(ValidationError):
            TestModel(codes=["usa", "xxx", "gbr"])
