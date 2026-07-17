# AI Test Automation — Python

[![CI](https://github.com/njmarshall/ai-test-automation-python/actions/workflows/ci.yml/badge.svg)](https://github.com/njmarshall/ai-test-automation-python/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-86%20passing-brightgreen.svg)](https://github.com/njmarshall/ai-test-automation-python)
[![Domains](https://img.shields.io/badge/domains-4-orange.svg)](https://github.com/njmarshall/ai-test-automation-python)
[![CI Jobs](https://img.shields.io/badge/CI%20jobs-7%20parallel-success.svg)](https://github.com/njmarshall/ai-test-automation-python/actions)

Production-grade AI-powered test automation framework across healthcare, insurance, fintech, and PetStore domains.

## Projects

| Project | API Tests | UI Tests | AI Tests |
|---|---|---|---|
| healthcare_fhir | FHIR R4 Patient, Encounter, Observation | HAPI FHIR explorer (Playwright) | 10 AI-generated |
| insurance | Policy CRUD (JSONPlaceholder) | JSONPlaceholder docs (Playwright) | 12 AI-generated |
| fintech | Coinbase market data, exchange rates, spot prices | Coinbase price page (Playwright) | 15 AI-generated |
| petstore | PetStore REST API (Swagger) | Swagger UI (Playwright) | planned |

## Test Coverage
- 86 passed, 1 skipped across all 4 projects
- 37 AI-generated tests via Anthropic SDK
- 12 Playwright UI tests across all projects
- 7 parallel CI jobs running on every push

## Async Polling Patterns
- TimeoutStrategy — Finix payment approval pattern (max 15s timeout)
- FixedRetryStrategy — Indeed email delivery pipeline (fixed retries)
- ExponentialBackoffStrategy — HEAVY.AI GPU cluster HA recovery (backoff)
- Reusable AsyncPoller in shared/async/ — Strategy pattern, 3 algorithms
- EventSequencer validates event ORDER and COMPLETENESS (Indeed email pipeline pattern)

## AI Co-Pilot Workflow
- Claude Chat for architecture decisions and design patterns
- Claude Code for automated test fixing loops and surgical fixes
- StalenessDetector flags stale tests before CI runs
- AI test generators for FHIR, Insurance, and Fintech domains

## Stack
Python 3.13, pytest, httpx, Playwright, Anthropic SDK, Pydantic, Faker, pytest-rerunfailures

## Design Patterns
Singleton, Facade, Factory, CRTP, Template Method, Fluent Interface, SOLID

## Published Article
[How I Built a 73-Test AI-Powered Test Framework Across 4 Domains Using Claude](https://www.linkedin.com/pulse/how-i-built-73-test-ai-powered-test-framework-across-4-neil-marshall-oefac/)

*Last updated: July 2026*
