from plugin.atelier.redaction import redact, redact_text


def test_redacts_headers_tokens_and_assignments() -> None:
    value = redact(
        {
            "Authorization": "Bearer abc.def.ghi",
            "nested": ["API_KEY=secret-value", "use " + "sk-" + "exampletoken123456"],
        }
    )

    assert value["Authorization"] == "[REDACTED]"
    assert value["nested"] == ["API_KEY=[REDACTED]", "use [REDACTED]"]


def test_preserves_non_secret_text() -> None:
    assert redact_text("expert returned evidence") == "expert returned evidence"
