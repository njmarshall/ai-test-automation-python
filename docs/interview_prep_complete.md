# AI Test Lead Interview Prep Guide
## Neil Marshall — Senior SDET and AI Test Automation Architect

---

## How to Use This Guide

Read one question per day. Say the short answer out loud. Study the code example. Sleep on it.

---

## Question 1 — The Opener

### The Question
> "Tell me about yourself and your recent work."

### What the Interviewer Wants
They want to know in 60 seconds: who you are, what you built, and why it matters. They are deciding whether to keep listening.

### Simple English Explanation
You are a Senior SDET with 15 years of experience who built an AI-powered test framework from scratch. It has 136 tests across 4 business domains. It uses Claude to generate tests automatically. It has 4 AI quality pillars built in. It has a self-healing agent that fixes its own broken tests.

### The Short Answer (memorize this)
> "I am a Senior SDET and AI Test Automation Architect with 15 years of enterprise experience at Salesforce, Microsoft, Indeed, and Finix. Over the past several months I built an AI-powered test framework in Python from scratch with 136 tests across 4 domains — healthcare FHIR R4, insurance, fintech, and PetStore. It implements all 4 AI quality pillars: Evaluation, Guardrails, Observability, and Orchestration. Most recently I completed the SelfHealingAgent — it detects failing tests, generates a fix via Claude, validates the fix with OutputGuard, and requires human approval before applying anything. My father was a family doctor which drives my passion for healthcare AI quality."

### What a Staff/Principal SDET Would Add
> "Note the human approval checkpoint. An agent that commits without approval is a liability, not an asset. Senior engineers build systems they can trust, not just systems that are impressive."

### Watch Out For
- Say **FHIR R4** not FHIR F4
- Name ALL 4 pillars — Evaluation, Guardrails, Observability, Orchestration
- Always mention human approval in SelfHealingAgent

---

## Question 2 — Guardrails

### The Question
> "You mentioned Guardrails. Can you explain what problem they solve and walk me through your implementation?"

### What the Interviewer Wants
They want to know you understand BOTH sides — input and output. One side without the other is incomplete.

### Simple English Explanation

Think of guardrails like airport security — checks on the way IN and checks on the way OUT.

**Input side problem:**
A developer copies a real patient payload from staging into a test prompt. It contains a real name, SSN, and medical record number. They send it to Claude without noticing. That PHI has now crossed the AI boundary — a HIPAA risk.

**Output side problem:**
Claude generates test code that accidentally contains a hardcoded password or exposed API key. That code goes straight into the codebase without anyone checking.

### The Code Example

**Input Guard — before sending to Claude:**
```python
guard = InputGuard()

result = guard.scrub_with_report(
    "Generate tests for Patient John Smith, SSN 123-45-6789"
)

print(result.scrubbed)
# Generate tests for Patient [NAME], SSN [SSN]

print(result.items_found)
# ["name", "ssn"]
```

**Output Guard — after Claude responds:**
```python
guard = OutputGuard()
result = guard.validate(generated_code)

if not result.passed:
    print(result.failures)
    # ["Unsafe content detected: hardcoded password"]
    # Fix is rejected — never reaches the codebase
```

### The Short Answer (memorize this)
> "Guardrails work on two sides. On the input side, before sending to Claude, my InputGuard strips PHI — patient names, SSNs, emails, MRNs — so sensitive data never crosses the AI boundary. On the output side, after Claude responds, my OutputGuard validates the generated code — checking for hardcoded passwords, exposed API keys, and syntax errors before it gets merged. Neither guard makes a system HIPAA compliant alone, but together they reduce two important classes of risk."

### What a Staff/Principal SDET Would Say
> "The distinction between scrubbing and blocking matters. In development, silent scrubbing allows work to continue. In production pipelines, strict mode should raise an error so engineers fix the source data. Always design guardrails with both modes."

### Watch Out For
- Always mention BOTH sides — input AND output
- HIPAA compliance — guardrails reduce risk, they do not make you compliant
- Strict mode exists for environments that need hard stops

---

## Question 3 — Observability

### The Question
> "What does your AiObserver actually track and why does drift detection matter?"

### What the Interviewer Wants
They want to know you understand that AI quality degrades gradually, not suddenly. Observability catches the slow decline before it becomes a hard failure.

### Simple English Explanation

Think of AiObserver like a car dashboard. You don't wait for the engine to stop before checking the oil. You watch the gauge every day.

**What it records on every Claude API call:**
- Duration — how long did it take?
- Input tokens + output tokens — how much data?
- Cost in dollars — how much did it cost?
- Quality score — how good was the output?
- Errors — did anything fail?

**Why drift detection matters:**
AI quality does not fail suddenly. It declines gradually:
```
Week 1: quality score 0.92
Week 2: quality score 0.81
Week 3: quality score 0.68  ← drift detected here
Week 4: quality score 0.51  ← hard failure here
```

Without drift detection you find out in Week 4.
With drift detection you find out in Week 3 — before users are affected.

### The Code Example
```python
observer = AiObserver()

with observer.observe("fhir_test_generation") as obs:
    message = claude.messages.create(...)
    obs.record_tokens(
        input_tokens=message.usage.input_tokens,
        output_tokens=message.usage.output_tokens,
    )
    obs.record_quality(0.86)  # from DeepEval

print(observer.summary())
# AI Observer Summary
#   Total calls  : 1
#   Total tokens : 3,241
#   Total cost   : $0.0584
#   Avg duration : 1,847ms
#   Avg quality  : 0.86
#   Drifting     : False

# Drift detection — checks last 5 calls
print(observer.is_drifting(threshold=0.7, window=5))
# True = problem detected early
```

### The Short Answer (memorize this)
> "My AiObserver records four things on every Claude call: duration, tokens, cost, and quality score. The most important is drift detection. It checks the last 5 scored calls — if the average falls below 0.7 it flags drift automatically. This catches quality decline gradually, before it becomes a hard failure. Same principle I used at Indeed with Datadog alerting — know about problems before your users do."

### What a Staff/Principal SDET Would Say
> "Observability without a response plan is just logging. The value is in what you do when drift is detected. Does the system alert someone? Pause generation? Trigger a re-evaluation run? Connect your AiObserver to your SelfHealingAgent and the story becomes complete."

### Watch Out For
- Say "last 5 calls, threshold 0.7" — shows you built it, not just read about it
- Connect to Indeed/Datadog story — real production experience
- Drift is gradual decline, not sudden failure

---

## Question 4 — SelfHealingAgent / Orchestration

### The Question
> "Walk me through your SelfHealingAgent. What does it do and why is human approval important?"

### What the Interviewer Wants
They want to know you built something real, understand the safety implications, and can explain all 4 pillars working together.

### Simple English Explanation

Without SelfHealingAgent — when CI fails at 3am:
```
You wake up → read error → figure out fix →
write fix → test → commit → sleep
Total: 45-60 minutes
```

With SelfHealingAgent — when CI fails at 3am:
```
Agent wakes up (not you) → reads error →
scrubs prompt → asks Claude to fix →
validates fix → asks YOU to approve →
Done
Total: 30 seconds of your time
```

### The 6 Steps with Code

```python
agent = SelfHealingAgent(require_approval=True)

result = agent.heal(
    failing_test_path="projects/healthcare_fhir/api/tests/test_patient.py",
    error_message="AssertionError: Expected 201, got 422",
    spec_context="POST /Patient — FHIR R4 Patient creation",
)

# Step 1: Read the failing test file
# Step 2: Build fix prompt
# Step 3: InputGuard scrubs PHI          ← GUARDRAILS
# Step 4: Claude generates fix           ← AI GENERATION
# Step 5: OutputGuard validates fix      ← GUARDRAILS
# Step 6: Human approval checkpoint      ← SAFETY
#         AiObserver records everything  ← OBSERVABILITY

print(result.summary())
# Healing result : PASS
# Cost           : $0.0156
# Duration       : 1847ms
```

### Why Human Approval Matters
An agent that commits without approval is dangerous. What if Claude generates a fix that passes OutputGuard but breaks a different test? What if the fix is correct but the wrong file? Human approval is the safety net that makes the agent trustworthy in production.

### The Short Answer (memorize this)
> "When a test fails in CI, the SelfHealingAgent reads the error, scrubs the fix prompt with InputGuard to protect PHI, asks Claude to generate a fix, validates with OutputGuard — checking syntax, no hardcoded passwords, no exposed API keys — then requires human approval before applying anything. AiObserver records the cost and speed of every healing attempt. All 4 pillars working together in one coordinated loop."

### What a Staff/Principal SDET Would Say
> "The human approval checkpoint is what separates a production-ready agent from a demo. Any engineer can build an agent that generates fixes. A senior engineer builds one that knows when NOT to act autonomously. That distinction shows architectural maturity."

### Watch Out For
- Name all 4 pillars in the answer
- Always mention human approval — it's the key differentiator
- "All 4 pillars working together" — this is the money phrase

---

## Question 5 — Strategic Thinking

### The Question
> "If you could only add ONE more capability to your framework tomorrow, what would it be and why?"

### What the Interviewer Wants
They want to see strategic thinking. Not "more tests" or "more features" — they want to know you understand architectural gaps and business risk.

### Simple English Explanation

**Why Contract Testing:**

Your framework currently validates API responses:
```
Test sends POST /Patient
API returns 201 with Patient resource
Test checks status and resource type
```

But what if the API changes its schema without notice?
```
Version 1: { "resourceType": "Patient", "id": "123" }
Version 2: { "resource": { "type": "Patient", "id": "123" } }
```

Your test still passes on Version 1.
Your production integration breaks on Version 2.
Nobody knows until a patient record is lost.

Contract testing catches this BEFORE deployment.

### The Short Answer (memorize this)
> "Contract testing. My framework validates API responses but not the CONTRACT between producer and consumer. At a healthtech company where FHIR services talk to each other, a breaking contract change could affect patient data integrity before anyone notices. Pact contract tests would catch incompatible changes at the service boundary, before they reach production. That is the gap that hurts most in a distributed healthcare system."

### What a Staff/Principal SDET Would Say
> "Contract testing is the difference between testing in isolation and testing integration points. Every distributed system eventually breaks at the boundaries. Senior engineers instrument those boundaries first."

### Watch Out For
- Pick ONE — not two or three
- Give the business risk, not just the technical gap
- Healthcare context — patient data integrity is the stakes

---

## One-Page Quick Reference

| Question | Key Phrase | Watch Out For |
|---|---|---|
| Q1 Opener | "136 tests, 4 domains, 4 AI pillars, SelfHealingAgent" | Say FHIR **R4** not F4 |
| Q2 Guardrails | "Input side scrubs PHI. Output side validates code." | Mention BOTH sides |
| Q3 Observability | "Last 5 calls, threshold 0.7, drift before failure" | Connect to Datadog/Indeed |
| Q4 SelfHealingAgent | "All 4 pillars, human approval always" | Name InputGuard + OutputGuard |
| Q5 Strategy | "Contract testing — patient data integrity at stake" | Pick ONE, give business risk |

---

## The One-Line Map

> Evaluation scores quality. Guardrails keep it safe. Observability watches it live. Orchestration coordinates the steps. I built a working piece of each.

---

*Read this every morning before an interview. Say each short answer out loud at least once.*
