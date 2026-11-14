# Telegram bot

A person types or says a question to the Earth Buddy bot in Telegram and gets the answer back in the chat: the verdict headline, the short explanation, the key numbers, the sources, and a link that opens the full result in the web app. Priority P1. Estimate 1 hour.

The bot is another keyboard. A message goes through `reader.read`, `analyses.run`, and `explainer.explain` like typed text in the web app, so it answers every kind in `ANALYSES` and cannot change a number or a verdict.

## What the person does

1. Opens the bot and sends `/start` or `/help`. The bot greets in Khmer and English and shows a one-time reply keyboard with two buttons, `LANG_BUTTONS`: "🇰🇭 ខ្មែរ" and "🇬🇧 English".
2. Taps a language. A reply keyboard button sends its label as an ordinary message, so no callback handling exists. The bot answers with `telegram.help` in that language and a reply keyboard of `EXAMPLES[lang]`, one question per row. That keyboard stays open, so the person can keep tapping questions.
3. Sends a claim or a question, typed or tapped, in English or Khmer. A message with any Khmer letter (U+1780 to U+17FF) gets a Khmer answer, and any other message gets English. The rule runs on every message, so the bot keeps no per-chat state.
4. Sees "typing…" in the chat from the moment a question or voice message arrives until the reply does. `/start`, `/help`, and the language buttons reply at once, with no "typing…".
5. Gets one HTML reply (`parse_mode: HTML`, link previews off): a verdict emoji and the headline with its highlighted words bold, the student `short` with `**x**` as bold, one `• label  value` line per tile, and the sources in a collapsed quote. Below it sits one button, "Open the full result".
6. Taps the button. The web app runs the same question, as a share link does.
7. Or holds the mic and sends a voice message, in Khmer or English, up to `voice.CLIP_S` (20) seconds. The reply is the typed-text reply for the transcript, under a first line `🎤 <i>transcript</i>`, so the person sees what was heard.
8. When the reader cannot build a question, the reply names the missing fields (`word.field.*`, in the message language) and suggests a demo sentence. Text over 600 characters, a question an analysis rejects, or a NASA source failure each get one friendly line.

## Module

`earthbuddy/telegram.py` has one pure entry point. Only `server.py` imports it.

```python
def answer(update: dict, base_url: str) -> dict | None
# {"method": "sendMessage", "chat_id", "parse_mode": "HTML", "link_preview_options", "text", "reply_markup"}, or None for an update with no text or voice message
```

- It reads only `message.chat.id`, `message.text`, `message.voice`, and `message.from.language_code`. Edits, joins, stickers, and every other update return `None`.
- AI follows `net.ai_available()`, the same rule as the web app.
- The emoji comes from `EMOJI[result.verdict.level]`, one table.
- Every piece of dynamic text goes through `html.escape`. The text uses only `b` and `blockquote expandable`, both in Telegram's HTML subset. Help and error replies are escaped plain text. Only `/start` and the language buttons carry a reply keyboard. A result keeps its inline button, since a message holds one `reply_markup`.
- The button's URL is `{base_url}#q={code}`. `code` is the unpadded base64url of `{"question": result.question, "revision": 0}`, the same shape `shareHash` in `web/app.js` writes and `openLink` sends to `/api/run`.
- `QuestionError` and `DataSourceError` become a reply, never an error status. Telegram retries a webhook that fails, so the person would wait twice for nothing.
- Every sentence is a `telegram.*` key in `words.EN` and `words.KM`. `telegram.choose` is bilingual and lives only in `EN`.
- `EXAMPLES` holds only questions that answer. A test sends each one offline and expects a result.

## Replies go back in the response body

Telegram lets a webhook answer by returning a Bot API call as its response body. The route returns the `sendMessage` dict, and Telegram sends it. The reply itself makes no outbound call.

## Typing indicator

While the bot works on a question or a voice message, the chat shows "typing…". `_typing(chat_id)` in `telegram.py` is a context manager around the work in `answer`.

`/start`, `/help`, and the two `LANG_BUTTONS` labels are menu replies from `_menu`. They reply at once and make no Telegram call, since waiting on `sendChatAction` would only delay them.

- It needs `TELEGRAM_BOT_TOKEN`. Without it, it makes no call and the answer is the same.
- It posts `sendChatAction` with `{chat_id, action: "typing"}` at once, then every `TYPING_S` (4) seconds, from one background thread. Telegram clears the status after 5 seconds or when the bot's message arrives.
- When the work ends, it stops the thread and waits for an in-flight call (2-second timeout) to finish, so the indicator never lands after the reply.
- A failed call stops the indicator and logs a warning with the HTTP status only, since the URL holds the token. The answer does not change.

## Voice messages

`message.voice` is `{file_id, duration, mime_type?, file_size?}`, an OGG/Opus file. In order:

1. `duration` over `voice.CLIP_S` or `file_size` over `voice.MAX_CLIP_BYTES`: `telegram.voice_long`, with no file or KiriTTS call.
2. No `TELEGRAM_BOT_TOKEN`, or `voice.status()["available"]` false: `telegram.voice_off`, with no file or KiriTTS call.
3. `POST https://api.telegram.org/bot<TOKEN>/getFile` with `{file_id}` gives `result.file_path`. `GET https://api.telegram.org/file/bot<TOKEN>/<file_path>` gives the bytes. Both go through `net.post` and `net.get`, so the test seal covers them.
4. `voice.hear(Clip(audio, "audio/ogg", lang))`. `lang` is `km` when `from.language_code` starts with `km`, else `en`. It only picks the KiriTTS hint and the language of a failure line.
5. The transcript goes through the text path, so the answer's language follows the transcript's script, as for typed text.

Failures each get one line in the message language. `VoiceFailed` maps its reason to `telegram.voice_off`, `telegram.voice_limit`, or `telegram.voice_down`. An empty transcript gets `telegram.voice_empty`. A Telegram failure gets `telegram.voice_off`.

The bot token sits in every Telegram URL, and `DataSourceError` carries its URL. So `telegram.py` catches every download error itself and logs only the error's type. The 502 handler never sees a Telegram URL.

`api.telegram.org` is a message host, never a data host. `is_data_host` stays NASA only, and only `telegram.py` names the host (`tests/test_sources.py`).

The bot does not speak its answer. KiriTTS returns WAV, and a Telegram voice message must be OGG/Opus (or MP3 as audio), so it would need a transcode step on the server.

## HTTP API

| Method and path | Body or query | Returns |
|---|---|---|
| `POST /api/telegram` | a Telegram `Update`, header `X-Telegram-Bot-Api-Secret-Token` | the `sendMessage` dict, or `{}` |

- `TELEGRAM_WEBHOOK_SECRET` unset: 404. The route does not exist for a deploy without the bot.
- `TELEGRAM_BOT_TOKEN` unset: voice messages get `telegram.voice_off`, and the chat shows no "typing…". Text works without it.
- A header that does not match the secret (`hmac.compare_digest`): 403.

## Setup, once per deploy

1. Create the bot with BotFather in Telegram and copy its token. Set `TELEGRAM_BOT_TOKEN` to it on the deploy for voice messages and the typing indicator. The token never goes into the code.
2. Pick a random secret (letters, digits, `_` and `-`, up to 256 characters) and set `TELEGRAM_WEBHOOK_SECRET` to it on the deploy.
3. Register the webhook:

```sh
curl https://api.telegram.org/bot<TOKEN>/setWebhook -d url=https://<deploy>/api/telegram -d secret_token=<secret>
```

4. Send the bot "Cambodia is getting hotter and drier".

## Acceptance

`tests/test_telegram.py`, through `/api/telegram`, offline:

- A demo sentence returns `sendMessage` in HTML to the same chat. Its first line holds the headline, the text holds every tile, and the button's link decodes to a body `/api/run` accepts and answers with the same headline.
- `<` and `&` in the explainer `short` arrive escaped.
- `/start` offers both language buttons. Each button replies in its language with exactly `EXAMPLES[lang]` as the keyboard.
- Every example returns a result with the open button.
- A Khmer message the reader cannot place gets Khmer. An English one gets English.
- Text over 600 characters returns 200 with a reply.
- A sticker update returns 200 `{}`.
- A wrong secret returns 403. No secret configured returns 404.
- A voice message, with Telegram and KiriTTS stubbed, returns the typed-text reply for its transcript under `🎤 <i>transcript</i>`, with the open button. A Khmer transcript gets Khmer.
- With a bot token, `/start` and a language button return their keyboards and make no Telegram call.
- With a bot token, a question posts `sendChatAction` `{chat_id: 42, action: "typing"}` and returns the same reply as without one. Work longer than `TYPING_S` repeats the call. Without a token, no Telegram call happens.
- A `sendChatAction` 403 or 500 still returns the same reply with 200, and the token appears in neither the reply nor the log.
- A 60-second voice message gets `voice_long` with no `getFile` or KiriTTS call. No bot token gets `voice_off` with no network call.
- KiriTTS 429 gets `voice_limit`. An empty transcript gets `voice_empty`. A Telegram `getFile` 500 gets `voice_off`, and the token appears in neither the reply nor the log.

## Known gaps

- Telegram waits about 60 seconds for a webhook. A live NASA POWER point fetch that is slow can run past that. Telegram then retries the same update, and the cache makes the retry fast. The person may wait for the second try.
- `base_url` comes from the request. Behind a proxy that does not forward the scheme, the link starts with `http://` and the deploy redirects it.
