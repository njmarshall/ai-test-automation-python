"""
fhir_spec_loader.py
-------------------
Loads and parses a FHIR R4 OpenAPI specification.

Pattern : Facade — hides JSON parsing and HTTP fetching behind
          a clean load() interface
SOLID   : SRP — one class, one job: produce a clean spec dict
          OCP — extend with load_from_url() for live spec fetching

Supports two sources:
  1. Local JSON file  (default — fast, no network needed)
  2. Live URL fetch   (optional — always up to date)

The returned dict is a normalised summary — not the raw OpenAPI blob.
Only the fields the generator actually needs are extracted, keeping
the prompt concise and the token cost low.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.request import urlopen

HAPI_FHIR_R4_SPEC_URL = (
    "https://hapi.fhir.org/baseR4/api-docs"
)


class FhirSpecLoader:
    """
    Facade that loads a FHIR OpenAPI spec and returns a clean summary dict.

    Example
    -------
        loader  = FhirSpecLoader()
        summary = loader.load_from_url()
        # summary = loader.load_from_file("specs/fhir_r4.json")
    """

    # ------------------------------------------------------------------ #
    #  Public loaders                                                      #
    # ------------------------------------------------------------------ #

    def load_from_file(self, path: str | Path) -> dict:
        """
        Load spec from a local JSON file and return a normalised summary.

        Parameters
        ----------
        path : path to the OpenAPI JSON spec file
        """
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        return self._normalise(raw)

    def load_from_url(
        self,
        url: str = HAPI_FHIR_R4_SPEC_URL,
        timeout: int = 15,
    ) -> dict:
        """
        Fetch spec from a live URL and return a normalised summary.

        Parameters
        ----------
        url     : OpenAPI spec endpoint (defaults to HAPI R4 sandbox)
        timeout : HTTP timeout in seconds
        """
        with urlopen(url, timeout=timeout) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        return self._normalise(raw)

    def load_minimal_patient_spec(self) -> dict:
        """
        Return a hard-coded minimal FHIR Patient spec summary.

        Used when the live HAPI spec endpoint is unavailable or too large.
        Covers exactly the endpoints exercised by Phase 1 MVP tests.
        This is the safe fallback — always works, no network required.
        """
        return {
            "title":   "FHIR R4 Patient Resource",
            "version": "4.0.1",
            "base_url": "https://hapi.fhir.org/baseR4",
            "endpoints": [
                {
                    "method":      "POST",
                    "path":        "/Patient",
                    "summary":     "Create a new Patient resource",
                    "request_body": {
                        "resourceType": "Patient",
                        "active":       True,
                        "name": [{"use": "official", "family": "string", "given": ["string"]}],
                        "gender":    "male | female | other | unknown",
                        "birthDate": "YYYY-MM-DD",
                        "identifier": [{"system": "string", "value": "string"}],
                    },
                    "responses": {
                        "201": "Patient resource created — returns full Patient with id",
                        "400": "Invalid FHIR resource",
                        "422": "Unprocessable entity",
                    },
                },
                {
                    "method":   "GET",
                    "path":     "/Patient/{id}",
                    "summary":  "Read an existing Patient resource by id",
                    "responses": {
                        "200": "Patient resource returned",
                        "404": "Patient not found",
                        "410": "Patient deleted",
                    },
                },
                {
                    "method":   "PUT",
                    "path":     "/Patient/{id}",
                    "summary":  "Update an existing Patient resource",
                    "responses": {
                        "200": "Patient updated",
                        "201": "Patient created (upsert)",
                        "400": "Invalid resource",
                    },
                },
                {
                    "method":   "DELETE",
                    "path":     "/Patient/{id}",
                    "summary":  "Delete a Patient resource",
                    "responses": {
                        "200": "Deleted — OperationOutcome returned",
                        "204": "Deleted — no content",
                        "404": "Patient not found",
                    },
                },
                {
                    "method":   "GET",
                    "path":     "/Patient",
                    "summary":  "Search for Patient resources",
                    "parameters": [
                        {"name": "family",     "in": "query", "description": "Family name"},
                        {"name": "given",      "in": "query", "description": "Given name"},
                        {"name": "birthdate",  "in": "query", "description": "Birth date"},
                        {"name": "gender",     "in": "query", "description": "Gender"},
                        {"name": "_count",     "in": "query", "description": "Page size"},
                        {"name": "identifier", "in": "query", "description": "Identifier value"},
                    ],
                    "responses": {
                        "200": "Bundle of matching Patient resources",
                    },
                },
            ],
            "fhir_notes": [
                "All requests must use Content-Type: application/fhir+json",
                "All responses use resourceType field to identify the resource",
                "Errors return OperationOutcome resourceType with issue array",
                "Resource id is server-assigned on POST — do not supply it",
                "DELETE on HAPI sandbox returns 200 with OperationOutcome",
            ],
        }

    # ------------------------------------------------------------------ #
    #  Internal normaliser                                                 #
    # ------------------------------------------------------------------ #

    def _normalise(self, raw: dict) -> dict:
        """
        Extract only the fields the generator needs from a raw OpenAPI spec.
        Keeps prompt tokens low by discarding irrelevant schema detail.
        """
        info      = raw.get("info", {})
        paths     = raw.get("paths", {})
        endpoints = []

        for path, methods in paths.items():
            if "Patient" not in path:
                continue
            for method, detail in methods.items():
                if method.upper() not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                    continue
                endpoint: dict[str, Any] = {
                    "method":   method.upper(),
                    "path":     path,
                    "summary":  detail.get("summary", ""),
                    "responses": {
                        code: resp.get("description", "")
                        for code, resp in detail.get("responses", {}).items()
                    },
                }
                if "parameters" in detail:
                    endpoint["parameters"] = [
                        {"name": p.get("name"), "in": p.get("in"), "description": p.get("description", "")}
                        for p in detail["parameters"]
                    ]
                endpoints.append(endpoint)

        return {
            "title":     info.get("title", "FHIR API"),
            "version":   info.get("version", "unknown"),
            "base_url":  "https://hapi.fhir.org/baseR4",
            "endpoints": endpoints,
        }
