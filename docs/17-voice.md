# Voice

A person taps the mic, asks a question aloud in English or Khmer, and hears the short answer read back. KiriTTS (https://www.kiritts.com/docs/api) does both directions. Priority P1. Estimate 2.5 hours, plus a 15-minute probe that needs only the API key.

KiriTTS carries speech, never data. It sits beside `api.anthropic.com` in the allowed hosts of `docs/16-data-sources.md`, and it never supplies a number, a place name, or a source.

The mic is a keyboard and the voice is a reader. A recording becomes the sentence the person would have typed, and goes through `/api/read` and the card like typed text. The voice reads only an `Explanation` that `explain` returned. Voice never reaches `Question`, `Result`, or any analysis, so it cannot change a number or a verdict.

## What the person does

1. Taps the mic in the ask box. The label says "Sends your voice to KiriTTS to turn it into text." Speaks for up to 20 seconds, then taps again.
2. The words appear in the ask box and the card opens, as if typed. The person fixes a field if the app misheard, then presses **Run**. Voice never skips the card.
3. The result appears, then the short answer. A spoken question gets a spoken answer in the page language. A typed question gets a speaker button and stays silent until it is pressed.
4. With no key, a used-up credit limit, or KiriTTS down, the mic and speaker are hidden, or one line says "Voice is not available. You can still type." Nothing else changes.

## Module

`earthbuddy/voice.py` owns everything KiriTTS: the key, the URLs, the wire fields, the per-language table, the transcription prompt, the error mapping, and the link signature. It imports only `types`, `net`, and `catalog`. Only `server.py` imports it.

```python
class Voice(NamedTuple): name: str; hint: str | None; speed: float = 1.0    # hint None = KiriTTS detects the language
VOICES: dict[Lang, Voice] = {"en": Voice("Maly", "en"), "km": Voice("Maly", "km-KH")}   # the probe sets these
class Speech(NamedTuple): audio: bytes; mime: str

def status() -> dict                                    # {"available", "clip_s", "mimes"}; the `voice` key of /api/status
def hear(clip: Clip) -> str                             # "" when nothing was heard; raises VoiceFailed
def voiced(e: Explanation, lang: Lang) -> Explanation   # sets e.audio to a signed /api/say URL; e unchanged when voice is off
def say(text: str, lang: Lang, sig: str) -> Speech      # a bad sig raises QuestionError("sig") before any network call
```

- `available` is `KIRITTS_API_KEY` set and not `EB_OFFLINE`, the same rule as `net.ai_available()`. Offline mode and the tests make no KiriTTS call unless a test stubs the transport.
- `hear` sends the clip to `POST /v1/audio/transcriptions` with model `kiristt`, the table's `hint` as `language`, and a `prompt` built from catalog place names, so "Siem Reap" and "Tonle Sap" come back spelled right.
- `voiced` signs `lang`, voice, speed, and `short` with its `**` marks removed. The signature is an HMAC keyed by the API key. The voice speaks `short` only. The student `short` has no numbers (`docs/13-explainer.md`).
- `say` checks the signature, then sends `POST /v1/audio/speech` with model `kiritts` and `response_format: mp3`. A 200 that is not `audio/*` counts as `down`.

`earthbuddy/net.py` gains one generic door. It knows nothing about KiriTTS, the same way `get_json` knows nothing about POWER.

```python
class Posted(NamedTuple): body: bytes; content_type: str
def post(url: str, *, headers: dict, json: dict | None = None, data: dict | None = None,
         files: dict | None = None, timeout_s: float = 30) -> Posted
```

It uses the shared client, so the test seal covers it. No cache and no POWER slot. One retry on a transport error or a 5xx. A 4xx raises `DataSourceError` at once, and `voice.py` maps it to a reason.

## Types

```python
ClipMime    = Literal["audio/webm", "audio/mp4", "audio/ogg", "audio/wav"]
VoiceReason = Literal["off", "limit", "down"]
class Clip(_M):  audio: bytes; mime: ClipMime; lang: Lang    # audio is base64 in the JSON body, decoded and capped at MAX_CLIP_BYTES
class Heard(_M): text: str
class Explanation(_M): short: str; more: str; via: Literal["ai", "template"]; audio: str | None = None
class VoiceFailed(Exception): reason: VoiceReason
```

The clip arrives as base64 JSON, so the server needs no `python-multipart` and the browser uses the same `api()` helper as every other call. httpx builds the outgoing multipart.

## HTTP API

| Method and path | Body or query | Returns |
|---|---|---|
| `POST /api/hear` | `{audio: base64, mime, lang}` | `{text}` |
| `GET /api/say` | `t, lang, sig`, taken whole from `Explanation.audio` | audio, `Cache-Control: public, max-age=31536000, immutable` |
| `POST /api/explain` | unchanged | adds `audio: str \| None` |
| `GET /api/status` | | adds `voice: {available, clip_s, mimes}` |

Errors: KiriTTS trouble returns 503 `{error, kind: "voice", reason}` from a fourth handler. 401 and 403 map to `off`, 429 to `limit`, and anything else to `down`. It is not 502, because `DataSourceError` is the only 502 and a speaker failure is not a NASA failure. A bad clip or a bad signature is the existing 400 with `field`. A 503 carries no cache header.

## Browser

`web/voice.js` (about 50 lines) owns the one `MediaRecorder` and the one `Audio` element. It exposes `listen`, `stop`, `speak`, `hush`, `unlock`, and `canListen`. It reads `mimes` and `clip_s` from `/api/status`, so the limits have one home.

- The transcript lands in `S.text`, and `submit()` runs, the same function as Ctrl+Enter. `S.spoken = true` marks that the question was spoken.
- When `/api/explain` lands, `if (S.spoken && e.audio) speak(e.audio)`. The speaker button replays or stops it.
- `S.busy` gains `"hear"`. Each call keeps the newest-wins sequence number.
- iOS plays audio only inside a tap, so the mic tap plays a silent clip to unlock the `Audio` element.
- `web/i18n.js` gains the `voice.*` keys in `en` and `km`, including one per `VoiceReason`.

## The probe

Run this as soon as the key exists, before the row starts, in parallel with P0. It changes data in `VOICES`, never code. Record the answers under **Probe results** at the end of this doc.

1. `GET /v1/voices`. Does one voice read both languages well? If the probe picks two voices, `voiced` chooses the row from the text's script (Khmer letters U+1780 to U+17FF) instead of the page language, because a Khmer page can show an English fallback answer.
2. Time a 300-character speech request in each language. Over about 2 seconds means streaming with `stream_format: audio` behind the same `/api/say` URL.
3. Speak a Khmer sentence that holds "0.28 °C" and "2001". A native reader listens. If it sounds wrong, the fix goes in one function in `voice.py`.
4. Transcribe the five demo sentences, spoken in English and in Khmer, recorded as webm (Chrome) and mp4 (Safari), with and without the `language` hint and the prompt. If `kiristt` rejects webm, `voice.js` records 16 kHz WAV instead.
5. Play a `/api/say` link in iOS Safari. Safari sends Range requests, and a plain `Response` ignores them. If playback fails, `speak` fetches the audio into a blob URL instead.

## Build order

Row 14a, after Khmer (row 14), before the P2 rows. Speech out reads `Explanation` (row 10). Speech in needs the ask box and card (row 9). A spoken Khmer question needs the Khmer keyword reader, and a Khmer answer needs Khmer templates (row 14).

Inside the row, build speech out first (`voiced`, `say`, the speaker button), then speech in. Each half ships alone. If time runs out, cut speech in. A Khmer answer read aloud is the stronger moment in the pitch.

## Acceptance

- `VOICES` has one row per `Lang`.
- `voiced`, then `GET e.audio`, returns 200 with the immutable cache header. The stubbed KiriTTS saw one request whose `input` is `short` without `**`. The key is not in the URL.
- A changed `t` returns 400 `field: "sig"` with zero KiriTTS calls.
- `hear` sends the model, the hint, a prompt that names a catalog place, and the file with its mime. An empty transcript returns 200 `{text: ""}`.
- A wrong mime, bad base64, and an oversized clip each return 400 naming the field.
- 429 returns `limit`. 401 and 403 return `off`. Two 500s return `down`.
- With no key: `voice.available` is false, `voiced(e) is e`, `/api/hear` returns 503 `off`, and nothing touches the network. `/api/explain` returns the same `short`, `more`, and `via` with and without a key.
- `test_layers`: only `server` imports `voice`, and `voice.py` does not contain `httpx`.
- `test_sources`: `api.kiritts.com` is an allowed host, and only `voice.py` names it.
- The README's AI-use statement names KiriTTS for speech to text and text to speech.
- By hand, with the key, through `python run.py` and the Vercel deploy, on Android Chrome and iOS Safari: at least 4 of the 5 demo sentences reach a runnable card with no edit, in each language. Each answer plays in the page language. Write down the time from the second mic tap to the card, and from the explanation to the first sound.

## Not building

- The realtime WebSocket. A Vercel Python function cannot hold it, and a browser-direct socket puts the key in the page.
- Hands-free runs. The card needs a tap, because a misheard place name must be fixed before it runs.
- Speaking `more`, the tiles, or the method. Add a second signed link if someone asks.
- A server audio cache. Browser and CDN caching cover replays, and SQLite stays the NASA response cache only.
- The browser's own speech API. Khmer voices are missing on most devices.

## Known gaps

- A forged `Result` posted to `/api/explain` can get a signature for template-shaped text. That is the trust `/api/explain` already has, and it is narrower than an open speech endpoint.
- `/api/hear` cannot be signed. `MAX_CLIP_BYTES` and KiriTTS's rate limit (100 a minute) bound it.

## Reference

KiriTTS API reference: https://www.kiritts.com/docs/api.

## Probe results

Not run yet. Fill in voices, the transcription hint, latency, accepted formats, and the iOS Range result.
