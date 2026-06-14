# Evaluation set

`routing_cases.jsonl` is a small live-regression set for LLM routing.
Run the offline tests first, then call the deployed endpoint with these prompts and
check that each response intent matches `expected_intent`.

Important near-collisions:

- `daily volume` must route to `analyst`, not `standup`.
- `weekly volume` must route to `analyst`, not `weekly`.
- `weekly meeting summary` must route to `weekly`.

The offline test suite also covers deterministic fallback behavior, metrics,
impact ranking, weekly pack generation, and Jira flag idempotency.
