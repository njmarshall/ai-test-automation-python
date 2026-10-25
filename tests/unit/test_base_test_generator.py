"""
test_base_test_generator.py
---------------------------
Unit tests for shared.ai.test_generator.BaseTestGenerator.

The Anthropic client is patched at anthropic.Anthropic, so no network
calls are made and no real ANTHROPIC_API_KEY is needed. InputGuard,
OutputGuard and AiObserver run for real so the tests exercise their
actual interfaces.
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest

from shared.ai.test_generator import BaseTestGenerator


pytestmark = pytest.mark.unit


VALID_CODE = (
    "import pytest\n"
    "\n"
    "\n"
    "def test_patient_created() -> None:\n"
    "    assert 201 == 201"
)

SPEC = {"resource": "Patient", "endpoints": ["POST /Patient"]}


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #

class StubGenerator(BaseTestGenerator):
    """Minimal concrete subclass used to drive the Template Method."""

    def build_system_prompt(self) -> str:
        return "You are a pytest generator."

    def build_prompt(self, spec: dict) -> str:
        return f"Generate tests for {spec['resource']}"


def make_message(text: str, input_tokens: int = 120, output_tokens: int = 340) -> MagicMock:
    """Build a fake anthropic Message with content[0].text and usage."""
    message = MagicMock()
    message.content = [MagicMock(text=text)]
    message.usage.input_tokens  = input_tokens
    message.usage.output_tokens = output_tokens
    return message


@pytest.fixture
def mock_anthropic(monkeypatch):
    """Patch anthropic.Anthropic and set a dummy API key."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-key-for-unit-tests")
    with patch("anthropic.Anthropic") as anthropic_cls:
        client = anthropic_cls.return_value
        client.messages.create.return_value = make_message(
            f"```python\n{VALID_CODE}\n```"
        )
        yield anthropic_cls


@pytest.fixture
def create(mock_anthropic) -> MagicMock:
    """Shortcut to the mocked client.messages.create."""
    return mock_anthropic.return_value.messages.create


# ------------------------------------------------------------------ #
#  Tests                                                               #
# ------------------------------------------------------------------ #

class TestBaseTestGenerator:

    def test_generate_returns_code_without_fences(self, mock_anthropic) -> None:
        generator = StubGenerator()

        code = generator.generate(SPEC)

        assert code == VALID_CODE
        assert "```" not in code
        mock_anthropic.assert_called_once_with(api_key="dummy-key-for-unit-tests")

    @pytest.mark.parametrize(
        "raw",
        [
            f"```python\n{VALID_CODE}\n```",
            f"```\n{VALID_CODE}\n```",
            VALID_CODE,
        ],
        ids=["fenced-with-language", "fenced-without-language", "raw-no-fences"],
    )
    def test_extract_code_strips_fences(self, raw: str) -> None:
        assert BaseTestGenerator._extract_code(raw) == VALID_CODE

    def test_missing_api_key_raises_environment_error(self, monkeypatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with patch("anthropic.Anthropic") as anthropic_cls:
            with pytest.raises(EnvironmentError, match="ANTHROPIC_API_KEY environment variable is not set") as exc:
                StubGenerator()

        assert "export ANTHROPIC_API_KEY=your_key_here" in str(exc.value)
        anthropic_cls.assert_not_called()

    def test_template_method_calls_steps_in_order(self, create) -> None:
        generator = StubGenerator()
        tracker   = Mock()
        tracker.build_system_prompt.return_value = "SYSTEM"
        tracker.build_prompt.return_value        = "USER"
        tracker.attach_mock(create, "create")
        generator.build_system_prompt = tracker.build_system_prompt
        generator.build_prompt        = tracker.build_prompt

        generator.generate(SPEC)

        tracker.build_system_prompt.assert_called_once_with()
        tracker.build_prompt.assert_called_once_with(SPEC)
        assert [c[0] for c in tracker.mock_calls] == [
            "build_system_prompt",
            "build_prompt",
            "create",
        ]
        kwargs = create.call_args.kwargs
        assert kwargs["system"]   == "SYSTEM"
        assert kwargs["messages"] == [{"role": "user", "content": "USER"}]

    def test_input_guard_scrubs_prompt_before_sending(self, create) -> None:
        generator = StubGenerator()
        generator.build_prompt = lambda spec: (
            "Generate tests for Patient John Smith, SSN 123-45-6789, "
            "email john.smith@example.com"
        )

        generator.generate(SPEC)

        sent = create.call_args.kwargs["messages"][0]["content"]
        assert sent == (
            "Generate tests for Patient [NAME], SSN [SSN], email [EMAIL]"
        )
        for raw_phi in ("John Smith", "123-45-6789", "john.smith@example.com"):
            assert raw_phi not in sent

    def test_output_guard_failure_raises_value_error(self, create) -> None:
        create.return_value = make_message(
            "```python\nimport pytest\n\ndef helper() -> None:\n    pass\n```"
        )
        generator = StubGenerator()

        with pytest.raises(ValueError, match="failed output validation") as exc:
            generator.generate(SPEC)

        assert "No test methods found" in str(exc.value)

    def test_observer_records_tokens_and_metrics(self, create) -> None:
        create.return_value = make_message(VALID_CODE, input_tokens=1000, output_tokens=2000)
        generator = StubGenerator()

        generator.generate(SPEC)

        records = generator._observer.get_records()
        assert len(records) == 1
        assert records[0]["call_name"]     == "test_generation"
        assert records[0]["input_tokens"]  == 1000
        assert records[0]["output_tokens"] == 2000
        assert records[0]["total_tokens"]  == 3000

        metrics = generator.get_metrics()
        assert isinstance(metrics, str)
        assert "Total calls    : 1" in metrics
        assert "Total tokens   : 3,000" in metrics

    def test_subclass_without_abstract_methods_cannot_be_instantiated(self, mock_anthropic) -> None:
        class IncompleteGenerator(BaseTestGenerator):
            def build_prompt(self, spec: dict) -> str:
                return "only one step implemented"

        with pytest.raises(TypeError, match="build_system_prompt"):
            IncompleteGenerator()
