# Explainer

The explainer writes the plain-language answer under a result: two short sentences, then a few more for anyone who wants detail. Templates always work. With AI on, the model writes the text, and code checks every number before the text is shown. Priority P1. Estimate 1.5 hours.

## Input and output

```python
def explain(result: Result, audience: Audience, lang: str, ai: bool) -> Explanation
Audience = Literal["student", "policymaker", "researcher"]
class Explanation(BaseModel): short: str; more: str; via: Literal["ai", "template"]
```

## Audiences

| Audience | Short answer |
|---|---|
| student (default) | Everyday words. No numbers. |
| policymaker | What it means for decisions. At most one number. |
| researcher | At most 3 sentences, with the slope, the 95% interval, the test, and p. |

The UI shows the student version and a small switch for the other two.

## Templates

Write one template per verdict key, per audience, per language. Templates fill `{placeholders}` from `facts` only. The template set must cover every verdict key that `analyses.py` can return. A test enumerates the keys.

## AI writer

```python
client.messages.create(
    model=os.environ.get("EB_MODEL", "au.anthropic.claude-haiku-4-5-20251001-v1:0"),
    max_tokens=1024,
    system=[{"type": "text", "text": f"{SYSTEM} {brief.rule}", "cache_control": {"type": "ephemeral"}}],
    messages=[{"role": "user", "content": json.dumps({"headline": ..., "facts": ..., "audience": ..., "lang": ...})}],
    output_config={"format": {"type": "json_schema", "schema": {short: str, more: str}}},
)
```

### What each audience reads

One table in `explainer.py` holds what each audience reads and may write:

```python
class Brief(NamedTuple):
    rule: str        # the one audience line of the prompt
    numbers: bool    # False: a reply that holds a number other than a year of the record shows the template

BRIEFS: dict[Audience, Brief]   # student: numbers False; policymaker and researcher: numbers True
```

- The system text is `SYSTEM` plus that audience's `rule` and nothing about the other two. Each audience has one fixed system text, so the Bedrock prompt cache still hits.
- Every audience's model gets the headline and every fact. A tie or a doubt is often stated with a number ("8 others are too close to tell"). On 2026-11-15 a student model that got only the number-free facts called a tied ranking "clear".
- The template still gets every fact.

### Which languages a model writes

Each row of `net.PROVIDERS` names the languages that provider writes. Bedrock writes `en` and `km`. The self-hosted model writes the languages in `EB_LLM_LANGS`, a comma list that defaults to `en`. `net.model_writes(lang)` is false for an unknown `EB_LLM`. When it is false, `explain` returns the template and calls no model. A small model wrote English for 12 of 16 Khmer requests, so Khmer shows the reviewed template until the self-hosted model is set to write it.

### Self-hosted model

With `EB_LLM=selfhosted`, `net.ask_model` sends the same system text, user text and schema to an OpenAI-compatible server instead of Bedrock.

```python
net.post(f"{EB_LLM_BASE_URL}/chat/completions", headers={"Authorization": f"Bearer {EB_LLM_API_KEY}"}, json={
    "model": EB_LLM_MODEL, "max_tokens": 1024,
    "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
    "response_format": {"type": "json_schema", "json_schema": {"name": "reply", "strict": True, "schema": SCHEMA}},
}, timeout_s=EB_LLM_TIMEOUT_S)
```

- An HTTP error, a body that is not a chat completion, or `finish_reason` other than `stop` fails the call. The explainer shows the template.
- The text is `choices[0].message.content`. One leading `<think>...</think>` block is dropped before the JSON is read.
- The result's headline and facts go to that server instead of AWS. The sentence the person typed never goes to any model.
- The number check below applies the same way.

`SYSTEM` says the following:

1. Use only numbers that appear in `facts`, written exactly as they appear there.
2. Call a change clear only when `facts.certainty` says it is clear.
3. "Not clear" means the record cannot tell. It does not mean nothing is happening.
4. Never claim a cause.
5. Write the short answer in 2 sentences and under 45 words, with bold on 2 or 3 verdict words only. Write the longer answer in 3 to 5 sentences.
6. Write for the given audience, in the given language.

Then the audience rule. A student gets everyday words and no numbers. The rule allows only the years of the record, written as digits, and says to leave every other amount out and never spell a number in words. A policymaker gets what it means for decisions and at most one number. A researcher gets at most 3 sentences in the short answer, with the slope, the 95% interval, the test, and p.

## Checks on the reply

`explain` runs these in order. The first that fails shows the template.

1. Shape. The reply has a non-empty `short` string and a `more` string.
2. Language. A reply for `km` must be mostly Khmer script: more code points in U+1780 to U+17FF than ASCII letters, over `short` and `more` together. Latin terms such as "p-value" and "NASA" are normal inside Khmer.
3. Numbers. `numbers_ok` runs against the facts. When the audience's `numbers` is false, only the years of the record are allowed. A year in digits is one code can check. Told to write no digits at all, the model spelled the years out, and once wrote "two thousand" for 2001.
4. Bold. The first 3 `**...**` spans in `short` and in `more` keep their markers (`BOLD_MAX`). The rest lose them. Words and numbers never change.

## The number check

```python
def numbers_ok(text: str, facts: dict, years: set[int]) -> bool
```

1. Find every number token in the text, including Khmer digits converted to ASCII. Treat the minus sign and a decimal comma as part of the number.
2. Accept a token when it equals a formatted value in `facts`, or a year in the result's years. A negative fact also allows its size without the sign, so "fell by 25%" passes for −25%.
3. If any token fails, use the template, set `via = "template"`, and log the rejected text.

The check does not read the direction word beside a number. "Fell by 14%" also passes when the fact is +14%. The sign was never a direction guard, and in 24 accepted trend replies no direction was flipped.

An analysis whose facts name an interval as `<x>_95pct_range` also holds `ci_pct`, so a reply that says "95% range" passes.

This check is the reason `fmt` exists (`docs/03-stats.md`): facts and text use one number format.

## Rules

- A failed or refused model call falls back to the template. The person sees no error.
- A result whose facts cannot fill its template makes `POST /api/explain` return 400 `{error, kind: "request", field: "result"}`.
- The verdict, tiles, and charts never depend on the explanation.
- `POST /api/explain` runs after `/api/run`, so the result appears first and the text arrives a moment later.

## Acceptance

- Each verdict key has a student template in English. Khmer falls back to English until it is written.
- `numbers_ok` rejects "about 0.3 °C" when `facts` holds "0.28". It accepts "0.28".
- A stubbed model that invents a number yields `via: "template"`.
- A student model receives the headline and every fact. A student reply with a number other than a year of the record yields `via: "template"`.
- A Khmer request answered in English yields `via: "template"`.
- With AI off, `/api/explain` returns `via: "template"` and makes no network call.

## Measured

Measured on the production deploy on 2026-11-15, over the five demo sentences in `docs/14-web-ui.md` and the three audiences. "Accepted" means the reply passed every check and was shown. A rejected reply shows the template.

| Model and state | English replies accepted | Student answers that hold a number |
| --- | --- | --- |
| `qwen3-4b`, before the checks in this doc | 39 of 60 | 12 of 13 |
| Claude Haiku 4.5, before | 22 of 30 | 5 of 8 |
| Claude Haiku 4.5, after | 24 of 30 | 0 of 7 |

- Before, the result kind decided acceptance on `qwen3-4b`, not the audience: scan 3 of 12, trend 5 of 12, where 8 of 12, claim 11 of 12, rank 12 of 12. Scan and where facts had no `ci_pct`. A fact of −25% rejected "fell by 25%".
- With `lang: "km"`, 12 of 16 accepted `qwen3-4b` replies were written in English. That is why the self-hosted model writes English only by default.
- `qwen3-4b` has not been measured after these checks. The "after" row was measured before the student rule allowed years.
- Bedrock limits the request rate on this account. With two calls in flight, 76 of 90 failed at once and showed the template. One call every 7 seconds never failed that way.
- Code cannot check meaning. In 24 accepted `qwen3-4b` trend replies, 5 stated the fall as a fact although the certainty was "not clear".

## Reference

`~/earth-buddy/earth-buddy-analyst/earthbuddy/analyst.py`: `SYSTEM`, `ANSWER_FORMAT`, `AUDIENCES`, `narrate`, and the `_s_*` and `_n_*` templates.
