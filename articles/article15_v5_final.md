__Article 15  |  AI Test Automation Series__

__The Database Was Correct. The Customer Still Failed.__

*By Neil Marshall, Senior SDET and AI Test Automation Architect*

In Article 14, I described three observations that a complete test strategy should make:

- The API responded according to its contract.
- The committed database state reflects the intended operation.
- The downstream business effect is correct.

Article 14 concentrated on the second observation. It showed why an HTTP response cannot prove that the intended row was committed, the constraint held, or the migration matched the deployed schema.

Paul Kanaris, founder of the QACE Institute, then asked the question that changes the level of the test:

__*Did the customer accomplish what they needed to accomplish?*__

That question identifies the next capability boundary for my framework. Database validation remains essential, but it is evidence about implementation. It is not, by itself, proof of customer success.

# The Row Was Correct and the Journey Was Not

Consider this synthetic healthcare scenario. It is illustrative, uses no patient data, and does not represent a verified production execution.

A patient submits a prior authorization request through a portal. In this example the API returns 202 Accepted because adjudication continues asynchronously. The service persists the request, receives an approval, and stores the correct patient, procedure, status, and effective dates.

The portal projection does not update. The scheduling service still reports that the procedure is not authorized. The patient cannot confirm coverage or complete the intended booking and is told to resubmit.

__*Every database assertion can pass while the customer journey fails.*__

The exact HTTP status is part of the API contract. RFC 9110 defines 201 Created for a request that has created a resource and 202 Accepted for processing that has not completed. If an API creates an authorization request resource immediately, 201 may be correct even when adjudication remains pending. The test must distinguish creation of the request from completion of the business outcome.

# Implementation Evidence and Customer Outcome

Paul's distinction does not make database testing less important. It places database evidence at the correct level.

An API response, committed row, emitted event, portal projection, integration acknowledgement, and audit record are observations. We combine them to answer a higher question: did the person complete the goal, within the promised time, without unsafe recovery work?

This matters because a team can optimize every component assertion and still miss the journey. An event can be published but never consumed. A portal API can return the right object while the visible page hides it. A provider service can receive coverage data while appointment booking rejects the procedure code.

A passing component test proves its component contract. A customer journey test evaluates whether those contracts compose into the promised outcome.

# Define the Customer Journey Oracle First

Before writing assertions, the team needs a customer journey oracle. This is not a single expected value. It is an agreed outcome contract owned by product, engineering, operations, domain experts, and quality engineering.

__Oracle field__

__Example definition__

Actor

A synthetic patient with an eligible plan and no existing authorization

Goal

Confirm authorization and proceed to appointment booking without calling or resubmitting

Start state

A valid request can be submitted in the controlled test environment

Terminal outcome

The portal shows approval and the booking service accepts the authorized procedure

Time budget

The approved state becomes usable within five minutes for this example organization

Required evidence

Status resource, portal display, booking decision, and correlation identifiers

Unacceptable outcome

Duplicate submission, false denial, blocked booking, or silent pending state

Recovery

A visible pending state and a supported retry or escalation path

Business owner

The accountable product or operations owner who approves the outcome definition

The five minute window is an example organizational policy, not a universal healthcare rule. The responsible business owner must define and approve the actual time budget, terminal outcome, and recovery behavior.

# Quality Ownership Across Boundaries

Component teams should own the quality of the services they build. That includes unit tests, API contracts, input validation, persistence behavior, and failure handling.

The ownership problem appears when the customer outcome crosses several components. Each team can satisfy its own contract while the complete journey still fails. Unless the organization assigns responsibility explicitly, journey verification can remain unowned between team boundaries.

This is not a criticism of engineering discipline. A software engineer writing a unit test for their service is not responsible for what the portal shows the patient three API hops downstream. That scope is correct for component ownership. The composition layer is a different boundary and requires a different kind of test.

Quality engineering provides a valuable system perspective at this boundary. An SDET who carries both development and quality engineering experience can read unfamiliar codebases, write integration tests that cross service boundaries, translate business outcomes into verifiable evidence, and explain failure evidence to product owners, engineers, and operations teams. That combination of skills is what the composition layer requires. It does not come from either role alone.

Paul Kanaris, founder of the QACE Institute, named this the Ownership and Visibility model. It assigns accountability at three distinct layers, each matched to the team that has both the competence and the mandate to own it.

__Layer 1 Implementation Testing (Component Layer)__

Owner: Dev Team. The development team tests from the system entry point through its contract terms. They prove that the API behaves as specified, that persistence behaves as designed, and that failure cases are handled correctly. This is the Integrity of the Contract. The dev team built the system and knows the contract. They are the right owner.

__Layer 2 Consumption Testing (Interface Layer)__

Owner: Consumer or Portal Team. The consuming team tests that they are reading the data correctly. They prove that the portal interprets the agreed status fields, handles states such as PENDING or DENIED according to the contract, and renders the correct state to the customer. This is the Fidelity of the Interface. The consumer team built the consumer and knows how they are reading the data. They are the right owner.

__Layer 3 Umbrella Layer (Quality and System Perspective)__

Owner: QA Engineering. Neither layer alone proves the complete customer journey. Both can be fully green while the customer still fails. In this model, Quality Engineering provides end to end observability for the complete journey from customer action to terminal outcome across every system boundary. When parts of the journey are not directly accessible, QA uses technical proxies such as API calls or status polling to advance the journey and observe the outcome. This is Orchestration, not redundant component testing.

__*“Devs: Prove the Implementation. Consumers: Prove the Interface. QA: Proves the Journey via Orchestration.” Paul Kanaris, QACE Institute*__

In some organizations the responsibility may belong to a software engineer, a platform team, or a shared quality function. The assignment should follow competence and mandate. What matters is that the assignment is explicit and the accountability is named, not left to fall between team boundaries.

The automation must also meet the same engineering standards expected of application code: design review, maintainability, observability, reliable failure evidence, and clear ownership.

This is not development transferring quality to SDETs. It is the organization assigning accountability for a system outcome that no component test can prove alone.

Product and domain owners define the promised customer outcome. Engineering supplies observable contracts and diagnostic evidence. The designated quality owner automates the journey, preserves evidence, and exposes where the promise stops being true. Operations contributes recovery behavior and service objectives. This is shared accountability with named ownership, not a test task silently assigned or contested between roles.

# Use the System to Prove the System

Paul described his practical method as using the system itself: enter data, update it, cancel or remove it through supported workflows, and observe whether the information and behavior change correctly.

That is the right default for a customer outcome test. Drive the workflow through public application surfaces. Observe the surfaces the customer and downstream actors depend on. Use a direct database query when you need to diagnose persistence or enforce a specific storage invariant, not as the primary oracle for customer success.

This distinction also protects the suite from query maintenance debt. A table rename, column split, or storage migration can break a direct SQL assertion even when customer behavior remains correct. That failure may be useful in a schema contract test, but it is noise in a journey test.

Direct database tests still belong in the strategy. Keep them focused, isolate their queries behind a small test data access layer, assign an owner, and update them with schema migrations. Do not duplicate internal SQL across customer journey tests.

# An Illustrative Customer Journey Contract Test

The following compact example is designed for a controlled staging environment with synthetic data. It validates a journey contract through supported surfaces. The test_patient fixture provisions the synthetic persona and registers cleanup. A database snapshot can be captured separately when the journey fails.

import time

from datetime import date

import requests

from playwright.sync_api import expect

TIMEOUT = (2, 10)

VISIBILITY_BUDGET_SECONDS = 300

def wait_for_approval(api, status_url):

    deadline = time.monotonic() + VISIBILITY_BUDGET_SECONDS

    while time.monotonic() < deadline:

        response = api.get(status_url, timeout=TIMEOUT)

        response.raise_for_status()

        if response.json()["status"] == "APPROVED":

            return response.json()

        time.sleep(5)

    raise AssertionError(

        "Authorization did not reach APPROVED within the journey budget")

def test_patient_can_use_approved_authorization(page, test_patient, settings):

    with requests.Session() as api:

        created = api.post(

            f"{settings.authorization_url}/authorizations",

            json={

                "patient_id": test_patient.id,

                "procedure_code": "99213",

                "requested_date": date(2026, 10, 15).isoformat(),

            },

            timeout=TIMEOUT,

        )

        assert created.status_code == 202

        request_id = created.json()["request_id"]

        status_url  = created.json()["status_url"]

        approved = wait_for_approval(api, status_url)

        assert approved["procedure_code"] == "99213"

        page.goto(

            f"{settings.portal_url}/patients/{test_patient.id}/authorizations")

        card = page.get_by_test_id(f"authorization_{request_id}")

        expect(card).to_contain_text("Approved")

        booking = api.post(

            f"{settings.scheduling_url}/appointments/precheck",

            json={

                "patient_id": test_patient.id,

                "procedure_code": "99213",

                "authorization_id": request_id,

            },

            timeout=TIMEOUT,

        )

        booking.raise_for_status()

        assert booking.json()["eligible"] is True

This test verifies three distinct things. The workflow reaches its approved business state through the status URL returned by the API, not by querying the database directly. The patient can see that state through the portal interface. The scheduling service accepts the authorization for the intended procedure.

It uses explicit network timeouts and a monotonic clock for the bounded wait. Python's time.monotonic function cannot move backward when the system clock changes. The Requests documentation also recommends explicit timeouts because calls otherwise have no default timeout.

The example still does not prove a real patient's comprehension, accessibility, trust, or clinical outcome. It proves a controlled customer journey contract for a synthetic persona. Usability research, accessibility testing, production telemetry, and support evidence answer different questions.

# What the Failure Evidence Should Contain

A useful journey failure should preserve enough evidence to locate the broken handoff without forcing the test to depend on every internal schema.

- The synthetic persona and journey contract version
- The request identifier and correlation identifier
- Observed status transitions and timestamps
- Portal screenshot or accessibility snapshot
- Booking decision and the relevant downstream response
- Relevant events and a targeted database snapshot for diagnosis
- Cleanup result for all synthetic records

The test should run only in an authorized environment with synthetic data, bounded waits, idempotent setup, reliable cleanup, and no destructive action against production. Evidence should identify customer impact without exposing protected information.

# What My Framework Does Today

I want to be precise about the current implementation.

The ExploratoryTestAgent proposes bounded probes that can reveal unexpected behavior. The SelfHealingAgent responds to known CI failures through classification, validation, human approval, and an audit trail.

Neither agent currently owns a complete customer journey oracle or verifies journey success across all required surfaces. That is not a hidden defect in the existing agents. It is the next capability boundary.

A proposed Phase 7 would introduce versioned journey contracts, evidence adapters for each surface, bounded waits, clear reason codes, and human review when the outcome oracle is missing or conflicted. It would not let a model invent customer success. The accountable humans would define the outcome, and the agent would collect and evaluate approved evidence.

# The Three Observations Restated

Observation one. The API responded according to its contract.

Observation two. The committed database state reflects the intended business operation.

Observation three. The customer completed the intended journey within the agreed conditions. API responses, rows, events, screens, integrations, and audit records are *evidence toward* that conclusion.

The third observation does not replace the first two. It depends on them and asks whether they compose into the result the organization promised.

# The Bottom Line

Do not ask the database to prove the customer succeeded. Ask it to prove the persistence facts it can actually know.

Then use the system from the outside in. Create, update, cancel, retrieve, and continue the workflow through supported surfaces. Define the terminal outcome, time budget, unacceptable harm, and recovery path before automation begins.

The database can be correct while the journey is broken. A mature quality strategy needs both truths.

For every high risk workflow, ask:

__*Did the customer accomplish what they needed to accomplish?*__

Then decide which evidence is necessary to answer honestly.

# Credit

Paul Kanaris, founder of the QACE Institute, contributed observations that shaped this article. His comment on Article 14 reframed the third observation as customer journey outcome rather than implementation evidence. His later reply raised two additional concerns: development responsibility for data integrity and the maintenance cost of direct database queries when backend implementations change. Those concerns informed my discussion of quality ownership across boundaries and outside in test design. His final review introduced the Ownership and Visibility model, the three layer accountability structure, and the clean assignment line that now anchors the quality ownership section. I am responsible for the design choices and conclusions presented here.

__Technical references. __RFC 9110 HTTP Semantics. Python time documentation. Requests timeout documentation.

__Open source framework: __github.com/njmarshall/ai-test-automation-python

__#TestAutomation #SDET #QualityEngineering #CustomerJourney #DataQuality #Healthtech #Python__

__*What customer journey has your team seen fail even though every component test passed?*__

