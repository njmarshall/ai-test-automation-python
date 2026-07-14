"""
async_poller.py
---------------
Reusable async polling strategies for test automation.

Real-world origin
-----------------
This module captures patterns from production SDET experience:

  Finix (payments)
    POST /transfers → 202 Accepted → poll until SUCCEEDED/FAILED
    POST /verifications → 202 → poll until APPROVED/DECLINED
    Max timeout: ~15 seconds for payment processing

  Indeed (email delivery)
    POST /email → 202 Queued → poll event sequence:
      QUEUED → SPAM_CHECK → CONTENT_SCAN → DELIVERED/BOUNCED
    Blacklist validation added latency — needed timeout strategy

  HEAVY.AI (GPU database HA)
    POST /cluster/failover → poll until REPLICA_PROMOTED
    High availability cluster regression — node recovery polling

Pattern : Strategy — three interchangeable polling algorithms
          (timeout, fixed retry, exponential backoff)
SOLID   : OCP — add new strategies without modifying existing ones
          SRP — each strategy class does one thing
          DIP — callers depend on AsyncPoller, not the strategy

Usage
-----
    # Finix-style: timeout-based polling (15 second max)
    poller = AsyncPoller(strategy="timeout", timeout_sec=15)
    result = poller.poll(
        fn=lambda: client.get_transfer_status(transfer_id),
        until=lambda r: r.json()["state"] in ("SUCCEEDED", "FAILED"),
    )

    # Indeed-style: fixed retry with delay
    poller = AsyncPoller(strategy="fixed", retries=5, delay_sec=3)
    result = poller.poll(
        fn=lambda: client.get_email_status(email_id),
        until=lambda r: r.status_code == 200,
    )

    # FAANG-style: exponential backoff
    poller = AsyncPoller(strategy="backoff", max_retries=5, base_delay_sec=1)
    result = poller.poll(
        fn=lambda: client.get_spot_price("BTC-USD"),
        until=lambda r: float(r.json()["data"]["amount"]) > 0,
    )
"""

from __future__ import annotations

import time
from typing import Any, Callable, Optional


# ------------------------------------------------------------------ #
#  Exceptions                                                          #
# ------------------------------------------------------------------ #

class PollingTimeoutError(Exception):
    """Raised when polling exceeds the configured timeout or retries."""
    pass


class PollingConditionError(Exception):
    """Raised when the polling condition is never satisfied."""
    pass


# ------------------------------------------------------------------ #
#  Strategy base                                                       #
# ------------------------------------------------------------------ #

class PollingStrategy:
    """
    Abstract base for polling strategies.
    Each strategy controls HOW we wait between attempts.
    """

    def wait(self, attempt: int) -> None:
        """Wait before the next poll attempt."""
        raise NotImplementedError

    def should_stop(self, attempt: int, elapsed_sec: float) -> bool:
        """Return True if polling should stop (timeout or max retries)."""
        raise NotImplementedError

    def description(self) -> str:
        """Human-readable description of this strategy."""
        raise NotImplementedError


class TimeoutStrategy(PollingStrategy):
    """
    Finix-style: poll until a maximum wall-clock time is exceeded.

    Best for: payment processing, background checks — where you know
    the SLA (e.g. 15 seconds) but not the exact number of retries.
    """

    def __init__(self, timeout_sec: float = 15.0, interval_sec: float = 1.0) -> None:
        self.timeout_sec  = timeout_sec
        self.interval_sec = interval_sec

    def wait(self, attempt: int) -> None:
        time.sleep(self.interval_sec)

    def should_stop(self, attempt: int, elapsed_sec: float) -> bool:
        return elapsed_sec >= self.timeout_sec

    def description(self) -> str:
        return f"timeout({self.timeout_sec}s, interval={self.interval_sec}s)"


class FixedRetryStrategy(PollingStrategy):
    """
    Indeed-style: fixed number of retries with a constant delay.

    Best for: email delivery pipelines, event sequence validation —
    where you know approximately how many steps the pipeline has.
    """

    def __init__(self, retries: int = 5, delay_sec: float = 3.0) -> None:
        self.retries   = retries
        self.delay_sec = delay_sec

    def wait(self, attempt: int) -> None:
        time.sleep(self.delay_sec)

    def should_stop(self, attempt: int, elapsed_sec: float) -> bool:
        return attempt >= self.retries

    def description(self) -> str:
        return f"fixed_retry({self.retries} retries, delay={self.delay_sec}s)"


class ExponentialBackoffStrategy(PollingStrategy):
    """
    FAANG-style: exponential backoff — waits 1s, 2s, 4s, 8s...

    Best for: distributed systems, high-availability cluster recovery —
    where hammering the server on failure makes things worse.
    Mirrors HEAVY.AI GPU cluster failover testing.
    """

    def __init__(
        self,
        max_retries:    int   = 5,
        base_delay_sec: float = 1.0,
        max_delay_sec:  float = 30.0,
    ) -> None:
        self.max_retries    = max_retries
        self.base_delay_sec = base_delay_sec
        self.max_delay_sec  = max_delay_sec

    def wait(self, attempt: int) -> None:
        delay = min(self.base_delay_sec * (2 ** attempt), self.max_delay_sec)
        time.sleep(delay)

    def should_stop(self, attempt: int, elapsed_sec: float) -> bool:
        return attempt >= self.max_retries

    def description(self) -> str:
        return f"exponential_backoff(max={self.max_retries}, base={self.base_delay_sec}s)"


# ------------------------------------------------------------------ #
#  AsyncPoller — the main interface                                    #
# ------------------------------------------------------------------ #

class AsyncPoller:
    """
    Reusable async polling engine for test automation.

    Supports three strategies:
      'timeout'  — Finix-style wall-clock timeout
      'fixed'    — Indeed-style fixed retries with constant delay
      'backoff'  — FAANG-style exponential backoff

    Example
    -------
        # Finix payment polling
        poller = AsyncPoller(strategy="timeout", timeout_sec=15)
        result = poller.poll(
            fn=lambda: client.get_transfer_status(transfer_id),
            until=lambda r: r.json()["state"] == "SUCCEEDED",
            description="payment transfer to SUCCEEDED",
        )
    """

    def __init__(
        self,
        strategy:       str   = "timeout",
        # Timeout strategy params
        timeout_sec:    float = 15.0,
        interval_sec:   float = 1.0,
        # Fixed retry params
        retries:        int   = 5,
        delay_sec:      float = 3.0,
        # Backoff params
        max_retries:    int   = 5,
        base_delay_sec: float = 1.0,
        max_delay_sec:  float = 30.0,
    ) -> None:
        if strategy == "timeout":
            self._strategy = TimeoutStrategy(
                timeout_sec=timeout_sec,
                interval_sec=interval_sec,
            )
        elif strategy == "fixed":
            self._strategy = FixedRetryStrategy(
                retries=retries,
                delay_sec=delay_sec,
            )
        elif strategy == "backoff":
            self._strategy = ExponentialBackoffStrategy(
                max_retries=max_retries,
                base_delay_sec=base_delay_sec,
                max_delay_sec=max_delay_sec,
            )
        else:
            raise ValueError(
                f"Unknown strategy '{strategy}'. "
                f"Choose from: 'timeout', 'fixed', 'backoff'."
            )

    def poll(
        self,
        fn:          Callable[[], Any],
        until:       Callable[[Any], bool],
        description: str = "condition",
    ) -> Any:
        """
        Poll fn() repeatedly until until(result) returns True.

        Parameters
        ----------
        fn          : callable that makes the API call each attempt
        until       : callable that checks if the result is final
        description : human-readable description for error messages

        Returns
        -------
        The last result from fn() when until() returned True.

        Raises
        ------
        PollingTimeoutError  : if strategy limit exceeded before condition met
        """
        attempt    = 0
        start_time = time.time()
        last_result: Any = None

        while True:
            last_result = fn()
            elapsed     = time.time() - start_time

            if until(last_result):
                return last_result

            if self._strategy.should_stop(attempt, elapsed):
                raise PollingTimeoutError(
                    f"Polling timed out waiting for '{description}' "
                    f"after {attempt + 1} attempts ({elapsed:.1f}s). "
                    f"Strategy: {self._strategy.description()}"
                )

            self._strategy.wait(attempt)
            attempt += 1

    def poll_for_status(
        self,
        fn:              Callable[[], Any],
        expected_status: int,
        description:     str = "HTTP status",
    ) -> Any:
        """
        Convenience method — poll until fn() returns expected HTTP status.

        Example
        -------
            poller.poll_for_status(
                fn=lambda: client.get_payment(payment_id),
                expected_status=200,
                description="payment to be retrievable",
            )
        """
        return self.poll(
            fn=fn,
            until=lambda r: r.status_code == expected_status,
            description=f"{description} (expecting HTTP {expected_status})",
        )
