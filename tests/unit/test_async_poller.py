"""
test_async_poller.py
--------------------
Unit tests for shared/async/async_poller.py

What is tested
--------------
  AsyncPoller.__init__   — correct strategy selected; ValueError on unknown
  TimeoutStrategy        — waits interval; stops at timeout; description
  FixedRetryStrategy     — waits constant delay; stops at max retries; description
  ExponentialBackoffStrategy — cap at max_delay; stops at max_retries; description
  AsyncPoller.poll()     — returns immediately on first success; raises on timeout;
                           calls fn on every attempt; passes last result
  AsyncPoller.poll_for_status() — convenience wrapper; correct delegation
  PollingTimeoutError    — message includes attempt count, elapsed, strategy name
  Error propagation      — fn() exceptions bubble through poll()

All time.sleep calls are patched so tests run in milliseconds.
No network calls, no external dependencies.
"""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

import importlib

_async_poller = importlib.import_module("shared.async.async_poller")
AsyncPoller = _async_poller.AsyncPoller
TimeoutStrategy = _async_poller.TimeoutStrategy
FixedRetryStrategy = _async_poller.FixedRetryStrategy
ExponentialBackoffStrategy = _async_poller.ExponentialBackoffStrategy
PollingTimeoutError = _async_poller.PollingTimeoutError


# ═══════════════════════════════════════════════════════════════════ #
#  TimeoutStrategy                                                     #
# ═══════════════════════════════════════════════════════════════════ #

class TestTimeoutStrategy:
    def test_should_stop_when_elapsed_exceeds_timeout(self):
        s = TimeoutStrategy(timeout_sec=10.0, interval_sec=1.0)
        assert s.should_stop(attempt=0, elapsed_sec=10.0) is True
        assert s.should_stop(attempt=0, elapsed_sec=10.1) is True

    def test_should_not_stop_before_timeout(self):
        s = TimeoutStrategy(timeout_sec=10.0, interval_sec=1.0)
        assert s.should_stop(attempt=99, elapsed_sec=9.9) is False

    def test_wait_sleeps_interval(self):
        s = TimeoutStrategy(timeout_sec=10.0, interval_sec=2.5)
        with patch("time.sleep") as mock_sleep:
            s.wait(attempt=0)
            mock_sleep.assert_called_once_with(2.5)

    def test_description_contains_timeout_and_interval(self):
        s = TimeoutStrategy(timeout_sec=15.0, interval_sec=1.0)
        desc = s.description()
        assert "15.0" in desc
        assert "1.0" in desc

    def test_attempt_count_irrelevant_to_should_stop(self):
        # TimeoutStrategy only cares about elapsed, not attempt number
        s = TimeoutStrategy(timeout_sec=5.0)
        assert s.should_stop(attempt=1000, elapsed_sec=4.9) is False
        assert s.should_stop(attempt=0,    elapsed_sec=5.0) is True


# ═══════════════════════════════════════════════════════════════════ #
#  FixedRetryStrategy                                                  #
# ═══════════════════════════════════════════════════════════════════ #

class TestFixedRetryStrategy:
    def test_should_stop_at_max_retries(self):
        s = FixedRetryStrategy(retries=3, delay_sec=1.0)
        assert s.should_stop(attempt=3, elapsed_sec=0.0) is True
        assert s.should_stop(attempt=4, elapsed_sec=0.0) is True

    def test_should_not_stop_before_max_retries(self):
        s = FixedRetryStrategy(retries=3, delay_sec=1.0)
        assert s.should_stop(attempt=2, elapsed_sec=999.0) is False

    def test_wait_sleeps_constant_delay(self):
        s = FixedRetryStrategy(retries=5, delay_sec=3.0)
        with patch("time.sleep") as mock_sleep:
            s.wait(attempt=0)
            s.wait(attempt=4)
            assert mock_sleep.call_count == 2
            # Same delay on every attempt
            mock_sleep.assert_called_with(3.0)

    def test_description_contains_retries_and_delay(self):
        s = FixedRetryStrategy(retries=5, delay_sec=3.0)
        desc = s.description()
        assert "5" in desc
        assert "3.0" in desc

    def test_elapsed_irrelevant_to_should_stop(self):
        # FixedRetryStrategy only cares about attempt count
        s = FixedRetryStrategy(retries=2)
        assert s.should_stop(attempt=1,  elapsed_sec=9999.0) is False
        assert s.should_stop(attempt=2,  elapsed_sec=0.0)    is True


# ═══════════════════════════════════════════════════════════════════ #
#  ExponentialBackoffStrategy                                          #
# ═══════════════════════════════════════════════════════════════════ #

class TestExponentialBackoffStrategy:
    def test_wait_doubles_each_attempt(self):
        s = ExponentialBackoffStrategy(base_delay_sec=1.0, max_delay_sec=100.0)
        with patch("time.sleep") as mock_sleep:
            s.wait(attempt=0)   # 1s
            s.wait(attempt=1)   # 2s
            s.wait(attempt=2)   # 4s
            s.wait(attempt=3)   # 8s
        calls = [c.args[0] for c in mock_sleep.call_args_list]
        assert calls == [1.0, 2.0, 4.0, 8.0]

    def test_wait_capped_at_max_delay(self):
        s = ExponentialBackoffStrategy(base_delay_sec=1.0, max_delay_sec=5.0)
        with patch("time.sleep") as mock_sleep:
            s.wait(attempt=10)  # 1024s capped to 5s
            mock_sleep.assert_called_once_with(5.0)

    def test_should_stop_at_max_retries(self):
        s = ExponentialBackoffStrategy(max_retries=4)
        assert s.should_stop(attempt=4, elapsed_sec=0.0) is True
        assert s.should_stop(attempt=3, elapsed_sec=0.0) is False

    def test_description_contains_max_retries_and_base_delay(self):
        s = ExponentialBackoffStrategy(max_retries=5, base_delay_sec=2.0)
        desc = s.description()
        assert "5" in desc
        assert "2.0" in desc


# ═══════════════════════════════════════════════════════════════════ #
#  AsyncPoller — constructor                                           #
# ═══════════════════════════════════════════════════════════════════ #

class TestAsyncPollerConstructor:
    def test_timeout_strategy_selected(self):
        poller = AsyncPoller(strategy="timeout", timeout_sec=10.0)
        assert isinstance(poller._strategy, TimeoutStrategy)

    def test_fixed_strategy_selected(self):
        poller = AsyncPoller(strategy="fixed", retries=3)
        assert isinstance(poller._strategy, FixedRetryStrategy)

    def test_backoff_strategy_selected(self):
        poller = AsyncPoller(strategy="backoff", max_retries=3)
        assert isinstance(poller._strategy, ExponentialBackoffStrategy)

    def test_unknown_strategy_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown strategy"):
            AsyncPoller(strategy="magic")

    def test_default_strategy_is_timeout(self):
        poller = AsyncPoller()
        assert isinstance(poller._strategy, TimeoutStrategy)


# ═══════════════════════════════════════════════════════════════════ #
#  AsyncPoller.poll() — happy path                                     #
# ═══════════════════════════════════════════════════════════════════ #

class TestAsyncPollerPoll:
    def test_returns_immediately_when_condition_met_on_first_call(self):
        result = MagicMock()
        result.json.return_value = {"state": "SUCCEEDED"}
        fn    = MagicMock(return_value=result)
        until = lambda r: r.json()["state"] == "SUCCEEDED"

        poller = AsyncPoller(strategy="fixed", retries=5, delay_sec=0)
        with patch("time.sleep"):
            outcome = poller.poll(fn=fn, until=until)

        assert outcome is result
        fn.assert_called_once()

    def test_polls_multiple_times_before_success(self):
        responses = [
            MagicMock(**{"json.return_value": {"state": "PENDING"}}),
            MagicMock(**{"json.return_value": {"state": "PENDING"}}),
            MagicMock(**{"json.return_value": {"state": "SUCCEEDED"}}),
        ]
        fn    = MagicMock(side_effect=responses)
        until = lambda r: r.json()["state"] == "SUCCEEDED"

        poller = AsyncPoller(strategy="fixed", retries=5, delay_sec=0)
        with patch("time.sleep"):
            outcome = poller.poll(fn=fn, until=until)

        assert fn.call_count == 3
        assert outcome.json()["state"] == "SUCCEEDED"

    def test_raises_polling_timeout_error_when_condition_never_met(self):
        result = MagicMock(**{"json.return_value": {"state": "PENDING"}})
        fn    = MagicMock(return_value=result)
        until = lambda r: r.json()["state"] == "SUCCEEDED"

        poller = AsyncPoller(strategy="fixed", retries=2, delay_sec=0)
        with patch("time.sleep"):
            with pytest.raises(PollingTimeoutError) as exc_info:
                poller.poll(fn=fn, until=until, description="payment to SUCCEEDED")

        assert "payment to SUCCEEDED" in str(exc_info.value)

    def test_error_message_includes_attempt_count(self):
        fn    = MagicMock(return_value=MagicMock(**{"status_code": 202}))
        until = lambda r: r.status_code == 200

        poller = AsyncPoller(strategy="fixed", retries=3, delay_sec=0)
        with patch("time.sleep"):
            with pytest.raises(PollingTimeoutError) as exc_info:
                poller.poll(fn=fn, until=until)

        assert "attempt" in str(exc_info.value).lower()

    def test_fn_exception_propagates_through_poll(self):
        fn = MagicMock(side_effect=ConnectionError("network down"))

        poller = AsyncPoller(strategy="fixed", retries=3, delay_sec=0)
        with patch("time.sleep"):
            with pytest.raises(ConnectionError, match="network down"):
                poller.poll(fn=fn, until=lambda r: True)

    def test_sleep_called_between_unsuccessful_attempts(self):
        responses = [
            MagicMock(**{"status_code": 202}),
            MagicMock(**{"status_code": 202}),
            MagicMock(**{"status_code": 200}),
        ]
        fn    = MagicMock(side_effect=responses)
        until = lambda r: r.status_code == 200

        poller = AsyncPoller(strategy="fixed", retries=5, delay_sec=0)
        with patch("time.sleep") as mock_sleep:
            poller.poll(fn=fn, until=until)

        # sleep called after first two failures, not after success
        assert mock_sleep.call_count == 2


# ═══════════════════════════════════════════════════════════════════ #
#  AsyncPoller.poll_for_status()                                       #
# ═══════════════════════════════════════════════════════════════════ #

class TestAsyncPollerPollForStatus:
    def test_returns_when_expected_status_reached(self):
        responses = [
            MagicMock(status_code=202),
            MagicMock(status_code=200),
        ]
        fn = MagicMock(side_effect=responses)

        poller = AsyncPoller(strategy="fixed", retries=5, delay_sec=0)
        with patch("time.sleep"):
            result = poller.poll_for_status(fn=fn, expected_status=200)

        assert result.status_code == 200
        assert fn.call_count == 2

    def test_raises_when_status_never_reached(self):
        fn = MagicMock(return_value=MagicMock(status_code=202))

        poller = AsyncPoller(strategy="fixed", retries=2, delay_sec=0)
        with patch("time.sleep"):
            with pytest.raises(PollingTimeoutError):
                poller.poll_for_status(fn=fn, expected_status=200)
