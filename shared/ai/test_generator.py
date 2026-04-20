"""
test_generator.py
-----------------
Reusable base class for AI-powered test generation.

Pattern : Template Method (BaseTestGenerator defines the skeleton;
          concrete subclasses like FhirTestGenerator fill in the steps)
SOLID   : OCP — open for extension (new domains), closed for modification
          DIP — callers depend on BaseTestGenerator, not Anthropic SDK directly
Design  : Anthropic SDK wrapped here once; all projects inherit for free.
          Output is always a raw Python string — saving to disk is the
          caller's responsibility (SRP).

Usage (concrete subclass)
-------------------------
    class FhirTestGenerator(BaseTestGenerator):
        def build_prompt(self, spec: dict) -> str:
            ...
        def build_system_prompt(self) -> str:
            ...
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

import anthropic


class BaseTestGenerator(ABC):
    """
    Abstract base for all AI-powered test generators.

    Template Method pattern:
      generate() is the invariant skeleton.
      build_system_prompt() and build_prompt() are the variant steps
      implemented by each domain-specific subclass.
    """

    DEFAULT_MODEL   = "claude-sonnet-4-6"
    DEFAULT_TOKENS  = 4096

    def __init__(
        self,
        model:      str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_TOKENS,
    ) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Export it before running the generator:\n"
                "  export ANTHROPIC_API_KEY=your_key_here"
            )
        self._client     = anthropic.Anthropic(api_key=api_key)
        self._model      = model
        self._max_tokens = max_tokens

    # ------------------------------------------------------------------ #
    #  Template Method — invariant skeleton                               #
    # ------------------------------------------------------------------ #

    def generate(self, spec: dict) -> str:
        """
        Generate pytest test code from an API spec dict.

        Steps (Template Method):
          1. build_system_prompt()  — subclass defines the AI persona
          2. build_prompt(spec)     — subclass builds the user message
          3. _call_api()            — base calls Anthropic SDK
          4. _extract_code()        — base strips markdown fences

        Returns
        -------
        str
            Raw Python source code ready to write to a .py file.
        """
        system_prompt = self.build_system_prompt()
        user_prompt   = self.build_prompt(spec)
        raw_response  = self._call_api(system_prompt, user_prompt)
        return self._extract_code(raw_response)

    # ------------------------------------------------------------------ #
    #  Variant steps — must be implemented by subclasses                  #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def build_system_prompt(self) -> str:
        """
        Return the system prompt that establishes the AI persona
        and output constraints for this domain.
        """

    @abstractmethod
    def build_prompt(self, spec: dict) -> str:
        """
        Return the user prompt that describes what tests to generate,
        given the parsed API spec dict.
        """

    # ------------------------------------------------------------------ #
    #  Invariant steps — shared by all subclasses                         #
    # ------------------------------------------------------------------ #

    def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        """Call the Anthropic Messages API and return the text response."""
        message = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
        )
        return message.content[0].text

    @staticmethod
    def _extract_code(raw: str) -> str:
        """
        Strip markdown code fences from the LLM response.

        Handles:
          ```python ... ```
          ``` ... ```
          Raw code with no fences
        """
        lines = raw.strip().splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        return "\n".join(lines).strip()
