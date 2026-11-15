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
    messages=[{"role": "user", "content": json.dumps({"headline": ..., "facts": shown, "audience": ..., "lang": ...})}],
    output_config={"format": {"type": "json_schema", "schema": {short: str, more: str}}},
)
```

### What each audience reads

One table in `explainer.py` holds what each audience reads and may write:

```python
class Brief(NamedTuple):
    rule: str        # the one audience line of the prompt
    numbers: bool    # False: the model gets only the facts that hold no number

BRIEFS: dict[Audience, Brief]   # student: numbers False; policymaker and researcher: numbers True
```

- The system text is `SYSTEM` plus that audience's `rule` and nothing about the other two. Each audience has one fixed system text, so the Bedrock prompt cache still hits.
- `shown` is every fact when `numbers` is true. Otherwise it is only the facts whose value is a non-empty string with no number in it. The headline goes to the model only when `numbers` is true or it holds no number.
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

Then the audience rule. A student gets everyday words and no numbers, and the rule says to write no digits at all. A policymaker gets what it means for decisions and at most one number. A researcher gets at most 3 sentences in the short answer, with the slope, the 95% interval, the test, and p.

## Checks on the reply

`explain` runs these in order. The first that fails shows the template.

1. Shape. The reply has a non-empty `short` string and a `more` string.
2. Language. A reply for `km` must be mostly Khmer script: more code points in U+1780 to U+17FF than ASCII letters, over `short` and `more` together. Latin terms such as "p-value" and "NASA" are normal inside Khmer.
3. Numbers. `numbers_ok` runs against `shown`, the facts the model received. Years are allowed only when the audience sees numbers. So any number in a student reply fails.
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
- A student model receives no number, and a student reply with any number yields `via: "template"`.
- A Khmer request answered in English yields `via: "template"`.
- With AI off, `/api/explain` returns `via: "template"` and makes no network call.

## Reference

`~/earth-buddy/earth-buddy-analyst/earthbuddy/analyst.py`: `SYSTEM`, `ANSWER_FORMAT`, `AUDIENCES`, `narrate`, and the `_s_*` and `_n_*` templates.
