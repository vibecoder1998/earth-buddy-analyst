# Reader: sentence to Question

The reader turns what a person typed into a `Draft`. The card shows the draft, and the person fixes it. Only a draft that parses into a `Question` is ever run. Priority P0. Estimate 2.5 hours.

One reader, the keyword reader, produces the `Draft`. It is pure Python and calls no model. An AI reader existed until 2026-11-15 and was removed: the web page never used it, and one reader means one behaviour to test.

## Flow

```python
def read(text: str, lang: str) -> ReadResult
# ReadResult = {draft: Draft, question: Question | None, missing: list[str]}
```

1. Refuse text that is empty or longer than 600 characters with a 400 error.
2. Call `read_keywords`.
3. Resolve a `place_name` to a `Point` with the geocoder (`docs/02-series.md`). The keyword reader sets `place_name` only when no catalog country or place matched, so a town such as Battambang arrives this way. A name the gazetteer does not know goes to `unmapped`.
4. Pass the raw output through `guard(raw, quote, via)`. Every input from outside goes through this one function: a typed sentence, a share link, and a card edit.
5. Try `Question.model_validate(draft.fields)`. On success, return the question. On failure, map each pydantic error to a field name in `missing`, such as `["region"]` or `["tests"]`.

## The guard

`guard` drops, without raising:

- unknown variable ids, region ids, and group ids
- duplicate variables, and tests past the 8th
- a direction outside `up`, `down`, `any`
- a lead or unmapped note that has a digit (`/[0-9០-៩０-９]/`), is longer than 80 characters, or is past the third
- a window outside the variable's years or shorter than `T.reliable` years. The window becomes `None`.

It also clamps `revision` to the range 0 to 99.

## Keyword reader

`read_keywords(text, lang)` is pure Python with no network call. It is deliberately broad. The card lets the person remove what does not fit.

- **Kind.** Check these patterns in order, and use the first match. Without a match, use `claim` when a direction word is present, else `trend`.

  | Kind | English cues |
  |---|---|
  | rank | "top N", "which country", "which province", "fastest", "rank", "compare A, B and C" |
  | relate | "linked", "related", "connected", "correlat", "goes with", "does more X mean less Y" |
  | extremes | "record", "wettest year", "hottest year", "unusual", "which month", "how hot was 2024" |
  | baseline | "than in the 1980s", "compared with", "than before", "since 1981" |
  | where | "where", "which part" |
  | scan | "what is changing in", "everything about" |

  Khmer cues live beside the English ones in `catalog.text.json`.

- **Variables.** Match catalog `keywords` as substrings of the lower-cased text. A Latin phrase must start at a word boundary, so "rain" does not match "Ukraine". Tests follow catalog order, except for `relate`, where they follow the sentence, so the first variable named is `x`.
- **Directions.** For each matched variable, look for its `up` and `down` words. "Hotter and drier" gives heat up and rain down. No direction word gives `any`.
- **Region.** Match place aliases, then country names, in both languages. The longest match wins. With no match, take capitalised words after "in", "at", "for", or "near" as `place_name`.
- **Window.** Read "since 2010", "from X to Y", "between X and Y", and "X–Y". Convert Khmer digits to ASCII first.
- **Rank group.** "Southeast Asia" maps to `southeast_asia_capitals`, "province" and "which regions" to `cambodia_provinces`, and "country" to `countries`.
- **Leads.** `NOT_MEASURED` lists things people ask about that no catalog variable measures: vegetation and forest cover, sea level, floods, crop yields. A match goes to `leads`, and the card says "We can't measure" it. Words a variable keyword already covers are taken out first, so "forest fires" is not a lead.

## Privacy

The sentence stays on the server. The reader sends nothing to AWS or to any other service.

## Acceptance

- The keyword reader turns each demo sentence (`docs/14-web-ui.md`) into a `Question` with no edits.
- "Cambodia is getting hotter and drier" gives `ClaimQ(Country("KHM"), [heat up, rain down])`.
- "Is it raining less in Ukraine?" does not match `rain` through "Ukraine". It matches `rain` through "raining" and the region `UKR`.
- `guard` drops a lead containing "3", an unknown variable, and a ninth test. It clamps revision 500 to 99.
- "Is tree cover declining in Mondulkiri?" returns the lead "vegetation and forest cover" and `missing: ["variable"]`.

## Reference

`~/earth-buddy/js/intake.js` (keyword reader and guard). `~/earth-buddy/api/intake.js` (prompt and schema). `~/earth-buddy/earth-buddy-analyst/earthbuddy/analyst.py` functions `parse` and `_special_intent` (intent cues).
