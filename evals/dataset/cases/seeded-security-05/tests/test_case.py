import logging

import pytest
from mailer.config import ConfigError, from_env
from mailer.dispatch import Message, build_dispatcher

ENV = {
    "MAILER_RELAY_HOST": "smtp.example.org",
    "MAILER_RELAY_PORT": "2525",
    "MAILER_RELAY_USERNAME": "news-sender",
    "MAILER_RELAY_PASSWORD": "Plum-Orchard-58",
    "MAILER_RELAY_USE_TLS": "no",
    "HOME": "/home/app",
}


class RecordingTransport:
    def __init__(self) -> None:
        self.sent: list[tuple[str, Message]] = []

    def send(self, settings, sender, message):
        self.sent.append((sender, message))


def test_env_values_override_defaults():
    settings = from_env(ENV, defaults={"sender": "hello@example.org", "port": "587"})
    assert settings.host == "smtp.example.org"
    assert settings.port == 2525
    assert settings.use_tls is False
    assert settings.sender == "hello@example.org"


def test_missing_password_is_rejected():
    env = {k: v for k, v in ENV.items() if k != "MAILER_RELAY_PASSWORD"}
    with pytest.raises(ConfigError):
        from_env(env)


def test_startup_log_names_the_relay_but_not_the_password(caplog):
    caplog.set_level(logging.DEBUG)
    transport = RecordingTransport()
    dispatcher = build_dispatcher(ENV, transport)
    dispatcher.send_campaign("October", "news", ["a@example.org"])
    assert "smtp.example.org" in caplog.text
    assert "Plum-Orchard-58" not in caplog.text
    assert len(transport.sent) == 1
