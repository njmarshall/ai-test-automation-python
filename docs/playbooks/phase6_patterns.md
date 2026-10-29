# Phase 6 Design Patterns — Plain English Playbook

## What Phase 6 is

Phase 6 added an **audit trail** to the self-healing agent.

Before Phase 6, when `SelfHealingAgent` fixed a broken test the result
lived only in the CI log — one run, then gone. In regulated environments
(HIPAA, PCI, IEC 62304) that is not acceptable. A human must be able to
review every automated change and sign off that it was correct. That means
a ticket, not a log line.

Phase 6 adds three things:
1. `JiraNotifier` — creates a JIRA ticket on every successful self-heal.
2. `SelfHealReport` — aggregates all healing events from one CI run into
   a single Markdown or JSON report for Allure.
3. `phase6_demo.py` — runs the full loop without API keys or JIRA
   credentials so it can be demonstrated in any environment.

Four design patterns make this work. This playbook explains each one
from scratch.

---

## Pattern 1 — Facade (JiraNotifier)

### The problem in plain English

The JIRA REST API is complex. You need to:
- Build a base64-encoded "Basic auth" header from your email and token.
- Construct a JSON payload in Atlassian Document Format (not plain text).
- Handle HTTP 200, 201, 401, 404, and network errors differently.
- Decide what "dry-run" means when credentials are missing.

If `SelfHealingAgent` did all of this directly, the healing logic would be
buried under 80 lines of HTTP plumbing. And if JIRA ever changed their API,
you would have to find and fix those 80 lines in the middle of your agent.

### What Facade does

A Facade puts a **simple door in front of a complicated room**. The room
still exists and does the real work. The door just has one handle.

```
SelfHealingAgent          JiraNotifier (Facade)     JIRA REST API
─────────────────         ─────────────────────     ─────────────
jira.notify(result)  -->  build auth header     -->  POST /issue
                          build JSON payload
                          handle HTTP errors
                          handle dry-run
                     <--  JiraTicketResult       <--  201 Created
```

`SelfHealingAgent` calls one method: `notify(result)`. It gets back one
object: `JiraTicketResult`. Everything in between is hidden.

### The code

```python
# In SelfHealingAgent.__init__:
self._jira = JiraNotifier()   # one line — the Facade is wired up

# In SelfHealingAgent.heal(), after a PASS:
jira_result = self._jira.notify(result)   # one call — the door handle
if jira_result.created:
    result.warnings.append(f"JIRA ticket: {jira_result.ticket_key}")
```

```python
# Inside JiraNotifier — the room behind the door:
class JiraNotifier:
    def notify(self, healing_result) -> JiraTicketResult:
        payload = JiraTicketPayload.from_healing_result(healing_result)
        if not self._config.is_configured:
            self._print_dry_run(payload)          # no credentials: print only
            return JiraTicketResult(created=False, dry_run=True)
        return self._post_ticket(payload)          # real credentials: POST
```

### Why it matters in an interview

"I used a Facade because the JIRA REST API has its own complexity: auth
headers, Atlassian Document Format for descriptions, and four different
HTTP error codes to handle. The Facade hides all of that. The agent calls
one method and gets one result back. If we replace JIRA with ServiceNow
tomorrow, we rewrite only the Facade, not the agent."

---

## Pattern 2 — Builder (SelfHealReport)

### The problem in plain English

A CI run may trigger the self-healing agent ten times. You want one
report that covers all ten events — totals, costs, which ones got JIRA
tickets. But you do not know how many events there will be until the run
finishes, and you want to add them one at a time as they happen.

### What Builder does

A Builder **constructs a complex object step by step**. Each step adds
one piece. A final `.build()` call assembles everything and returns the
finished object.

Think of it like building a sandwich at a counter. You say: "Add turkey.
Add cheese. Add lettuce." Each call returns the same counter (so you can
keep adding). When you say "done" the sandwich is handed to you, sealed.

```python
report = (
    SelfHealReport(run_id="ci-run-42")
    .add_healing(result_1, jira_1)   # returns self — keep chaining
    .add_healing(result_2, jira_2)
    .add_healing(result_3, jira_3)
    .build()                          # returns BuiltReport — sealed
)
```

The `.build()` call computes the totals (passed, rejected, cost) once
and freezes them. You cannot add more events after `.build()`.

### The code

```python
class SelfHealReport:
    def __init__(self, run_id: str = "local") -> None:
        self._run_id  = run_id
        self._entries = []          # accumulates events

    def add_healing(self, healing, jira) -> "SelfHealReport":
        self._entries.append(HealingEntry.from_results(healing, jira))
        return self                 # return self = chaining works

    def build(self) -> BuiltReport:
        passed  = sum(1 for e in self._entries if e.status == "PASS")
        cost    = sum(e.cost_usd for e in self._entries)
        return BuiltReport(         # immutable — see Pattern 3
            run_id=self._run_id,
            total_events=len(self._entries),
            passed=passed,
            ...
        )
```

### Why it matters in an interview

"I used Builder because the number of healing events in a CI run is not
known upfront. The Builder lets the agent add events one at a time as they
happen, then `.build()` computes everything once at the end. The chaining
syntax also makes the intent readable — you can see exactly what went into
the report from the call site."

---

## Pattern 3 — Value Object / Immutable Object (BuiltReport)

### The problem in plain English

After `.build()` returns a report, you want to be sure it cannot be
modified. If you save the report to a file and then someone adds another
event to the same object, the saved file and the in-memory object would
disagree. That is a compliance risk.

### What an Immutable Value Object does

A Value Object is an object that represents a **fixed value** — like a
date or a price. Once created, it cannot change. Its identity is its
content, not its memory address.

In Python the simplest way to achieve this is `@dataclass(frozen=True)`.
Frozen dataclasses raise `FrozenInstanceError` if you try to set any
attribute after creation.

```python
@dataclass(frozen=True)
class BuiltReport:
    run_id:        str
    generated_at:  str
    total_events:  int
    passed:        int
    rejected:      int
    jira_created:  int
    total_cost:    float
    entries:       tuple          # tuple not list — tuples are immutable too
```

You can call `report.to_markdown()` and `report.to_json()` and `report.save()`
as many times as you want. The data never changes. Every call produces
the same output.

### Why it matters in an interview

"BuiltReport is a frozen dataclass. After `.build()` no code can change
the counts or entries. That matters in a compliance context: the report
you print to Allure is the same report you write to disk, always.
I also used a tuple instead of a list for the entries field because
tuples in Python are immutable by design."

---

## Pattern 4 — Template Method (SelfHealingAgent.heal)

### The problem in plain English

The self-healing loop always follows the same steps in the same order:
1. Read the failing test.
2. Scrub the prompt (InputGuard).
3. Generate a fix (Claude).
4. Validate the fix (OutputGuard).
5. Ask for human approval.
6. Notify JIRA.

These steps never reorder. But the *implementation* of step 3 (how you
call Claude, which model, what parameters) could change — maybe for a
different domain you want a different prompt template.

### What Template Method does

Template Method defines **a skeleton of steps in a base class, with some
steps left open for subclasses to fill in**. The skeleton never changes.
The details can vary.

Think of a recipe card. The recipe always says: "1. Prep ingredients.
2. Cook. 3. Plate." The *how* of each step is where cooks differ. The
order never changes.

```python
class SelfHealingAgent:
    def heal(self, ...):          # THE TEMPLATE — always these steps
        test_code  = self._read_test(...)          # step 1
        safe_prompt = self._input_guard.scrub(...)  # step 2
        fix = self._generate_fix(safe_prompt)       # step 3 — overridable
        validation = self._output_guard.validate(fix)  # step 4
        if self._require_approval:
            self._request_approval(...)             # step 5 — overridable
        self._jira.notify(result)                   # step 6

    def _generate_fix(self, prompt):   # subclass can override this
        # default: call Claude claude-sonnet-4-6
        ...

    def _request_approval(self, ...):  # subclass can override this
        # default: print to terminal
        ...
```

In `phase6_demo.py` the mock patches `_generate_fix` and
`_request_approval` without changing `heal()` at all. That is the
Template Method paying off: the skeleton runs, only the pluggable steps
are swapped out for the demo.

### Why it matters in an interview

"SelfHealingAgent.heal() is a Template Method. The six steps of the
healing loop are fixed in the base class — InputGuard, OutputGuard,
human approval, JIRA notification — all in order. In the demo I mock
_generate_fix and _request_approval without touching heal() itself.
In production a healthcare domain subclass could override _generate_fix
to use a HIPAA-specific model. The skeleton stays the same."

---

## How the four patterns connect

```
SelfHealingAgent.heal()            <-- Template Method: fixed skeleton
  calls JiraNotifier.notify()      <-- Facade: one door into JIRA
  returns HealingResult

SelfHealReport                     <-- Builder: add events one at a time
  .add_healing(result, jira_result)
  .build()
  --> BuiltReport                  <-- Value Object: immutable, safe to save
        .to_markdown()
        .to_json()
        .save()
```

Each pattern solves exactly one problem:
- **Facade** — hides JIRA's complexity from the agent.
- **Builder** — accumulates events before the total is known.
- **Value Object** — locks the report after it is assembled.
- **Template Method** — keeps the healing skeleton stable while details vary.

---

## Quick reference — one-line definitions

| Pattern | One line |
|---|---|
| Facade | One simple method hides a complex subsystem |
| Builder | Build a complex object step by step, seal it with .build() |
| Value Object | An object that represents a fixed value and cannot change |
| Template Method | A base class defines the skeleton; steps can be overridden |

---

*Phase 6 — AI Test Automation Series — Neil Marshall, Marshall Test Engineering*
