# Safety-Constrained Refund Agent

An LLM agent that issues customer refunds by writing to a transactional database, built as an instrument for a single question.

**Where does a policy rule have to live in order to hold when the model does not follow it?**

The agent can do exactly two things that matter. Issue a refund, or escalate to a human. Every policy rule exists in exactly one identifiable place and can be moved between the prompt and the write transaction, which is what makes the comparison measurable rather than rhetorical.

Full write-up, including threats to validity and what a proper study would require: [`docs/where-the-constraints-live.pdf`](docs/)

---

## The design claim

Rules enforced in the prompt are a prior over outputs. Rules enforced in the write transaction are an invariant. The two fail in different directions under pressure, and the difference is observable if you instrument it.

Five rules live inside the function that writes, under a row lock on the order, with a uniqueness constraint on a derived idempotency key beneath that:

| Rule | Scope it is enforced over |
|---|---|
| Ownership | the order |
| Refund cap | each refund |
| Single write | each conversation |
| Refundable remainder | the order |
| Kill switch | global |

The prompt also describes most of these. That redundancy is deliberate. When the model violates a rule the prompt states and the transaction forbids, the **attempt** is recorded and the **effect** is not.

Every write attempt, allowed or refused, writes an audit row **in its own transaction**, so a refused attempt survives its own rollback. That table is what makes attempted violations countable separately from realised ones, and most of the findings depend on it.

> Note the scope column above. Nothing was enforced per order *across* conversations, and that gap is finding F5.

## Quickstart

```bash
# TODO: fill in from your actual setup
cp .env.example .env            # model key, database URL, Langfuse keys
docker compose up -d            # Postgres, Temporal
alembic upgrade head
python -m <pkg>.seed            # fixtures + annotated goal states
uvicorn <pkg>.api:app --reload
```

Requires Python 3.13 and Postgres.

## Architecture

```
FastAPI  ->  agent (pydantic-ai, typed output)  ->  tools (read)
                                                 ->  write path
                                                       |
                                          Temporal workflow (durable)
                                                       |
                                     enforcement + row lock + audit row
                                                       |
                                                   Postgres
```

The agent returns a typed object carrying a decision, an amount, a reason code and a cited policy article. There is no free-text path, so an unparseable answer is a caught error that escalates rather than a string someone parses hopefully.

## Evaluation

Grading is on **final database state**, not on transcripts. A case passes when the refunds table at the end of the episode equals the annotated goal state. Goal states were written before the agent existed, emitted by the seeding script in the same pass as the fixture rows.

| Set | n | What it tests |
|---|---|---|
| A | 70 orders, 16 archetypes | task fixtures weighted to boundaries |
| B | 30 | adversarial, 6 attack categories plus 5 controls that require action |
| C | 8 | multi-turn, simulated customer with a hidden goal |
| D | 15 | tools called directly with hostile arguments, no model in the loop |

```bash
# TODO: fill in from your actual setup
python -m <pkg>.eval run   --set A --prompt v3
python -m <pkg>.eval grade --run <run-id>
python -m <pkg>.eval report --compare v1 v2
```

**Collection and grading are decoupled.** Episodes are recorded as full trajectories with provenance covering prompt sha, dataset sha, model id, git sha and dirty flag, tokens, cost, latency and database state before and after. Grading replays only the write calls against a freshly seeded database, so it is deterministic, costs nothing, and can be re-run after enforcement code changes. Every model response is cached on disk under a key covering prompt sha, dataset sha, model, request text, order id and the write-enabled flag.

Conditions are three prompt versions against one pinned model at temperature 0, with a hard limit of 8 model calls per episode.

## What the measurements showed

Numbers are from a small, clustered, single-annotator study. Read the limitations below before quoting any of them.

- **Attempted and realised violations move independently.** Between two prompt versions, attempts to double-pay rose from 11 to 17 of 70 episodes while money overpaid fell from 33,200 to 8,400 minor units. A report containing only outcomes cannot distinguish a working defence from luck.
- **A zero attack-success rate can be produced by inaction.** Zero successful injections across 30 adversarial episodes, and 19 of those 30 produced no action at all. Under one prompt version, 0 of 8 multi-turn conversations reached a second turn, so a suite written to test grooming tested none.
- **Individually correct guards composed into a hole.** The cap was per refund, the single-write rule per conversation, the remainder per order, and nothing per order across conversations. Two sequential conversations moved 6,000 minor units under a 5,000 cap. Seventeen hand-written safety tests passed throughout, and the 70-case evaluation could not have caught it, because no fixture held two conversations against one order.
- **Transactional guards held in every condition.** No unauthorised write, no refund above cap or remainder, across roughly 108 episodes. By the rule of three that bounds the true rate at about 3%, and the paralysis above makes even that optimistic.

## Known limitations

- The adversarial fixtures and the simulated customer run on the **same model** as the agent, so the attacker is the defender and the attacks are in-distribution and polite.
- Adversarial cases are graded as a ceiling, which means **an agent that does nothing passes**. A refusal-validity rule is the fix and is not yet implemented.
- The 70 cases are 16 archetypes expanded into near-identical instances, so they are not independent draws. Every interval in the write-up should be read as the optimistic end of its range.
- **No held-out set.** Every case informed development.
- One annotator, unblinded, who also wrote the goal states, the attacks and the error analysis.
- Single domain. A refund is scalar, owned and idempotent, which is the friendliest possible case for transactional enforcement.

## Stack

Python 3.13, pydantic-ai, Postgres 17, SQLAlchemy, Alembic, Temporal, FastAPI, pytest, Testcontainers, Langfuse, Prometheus.
