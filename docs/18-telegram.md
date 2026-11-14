# Telegram bot

A person types a question to the Earth Buddy bot in Telegram and gets the answer back in the chat: the verdict headline, the short explanation, the key numbers, the sources, and a link that opens the full result in the web app. Priority P1. Estimate 1 hour.

The bot is another keyboard. A message goes through `reader.read`, `analyses.run`, and `explainer.explain` like typed text in the web app, so it answers every kind in `ANALYSES` and cannot change a number or a verdict.

## What the person does

1. Opens the bot and sends `/start` or `/help`. The bot replies with a greeting and the five demo sentences from `docs/14-web-ui.md`.
2. Sends a claim or a question, in English or Khmer. A message with any Khmer letter (U+1780 to U+17FF) gets a Khmer answer.
3. Gets one plain-text reply: the headline, a blank line, the student `short`, a blank line, each tile as `label: value`, `Sources:` with one source name per line, and the web link.
4. Opens the link. The web app runs the same question, as a share link does.
5. When the reader cannot build a question, the reply names the missing fields and suggests a demo sentence. Text over 600 characters, a question an analysis rejects, or a NASA source failure each get one friendly line.

## Module

`earthbuddy/telegram.py` has one pure entry point. Only `server.py` imports it.

```python
def answer(update: dict, base_url: str) -> dict | None
# {"method": "sendMessage", "chat_id": ..., "text": ...}, or None for an update with no text message
```

- It reads only `message.chat.id` and `message.text`. Edits, joins, stickers, and every other update return `None`.
- AI follows `net.ai_available()`, the same rule as the web app.
- The link is `{base_url}#q={code}`. `code` is the unpadded base64url of `{"question": result.question, "revision": 0}`, the same shape `shareHash` in `web/app.js` writes and `openLink` sends to `/api/run`.
- `QuestionError` and `DataSourceError` become a reply, never an error status. Telegram retries a webhook that fails, so the person would wait twice for nothing.
- Every sentence is a `telegram.*` key in `words.EN`. Khmer falls back to English through `Words` until someone translates them.

## No outbound HTTP

Telegram lets a webhook answer by returning a Bot API call as its response body. The route returns the `sendMessage` dict, and Telegram sends it. So the code holds no bot token, `net.py` gains nothing, and `docs/16-data-sources.md` gains no host.

## HTTP API

| Method and path | Body or query | Returns |
|---|---|---|
| `POST /api/telegram` | a Telegram `Update`, header `X-Telegram-Bot-Api-Secret-Token` | the `sendMessage` dict, or `{}` |

- `TELEGRAM_WEBHOOK_SECRET` unset: 404. The route does not exist for a deploy without the bot.
- A header that does not match the secret (`hmac.compare_digest`): 403.

## Setup, once per deploy

1. Create the bot with BotFather in Telegram and copy its token. The token never goes into the code or the deploy.
2. Pick a random secret (letters, digits, `_` and `-`, up to 256 characters) and set `TELEGRAM_WEBHOOK_SECRET` to it on the deploy.
3. Register the webhook:

```sh
curl https://api.telegram.org/bot<TOKEN>/setWebhook -d url=https://<deploy>/api/telegram -d secret_token=<secret>
```

4. Send the bot "Cambodia is getting hotter and drier".

## Acceptance

`tests/test_telegram.py`, through `/api/telegram`, offline:

- A demo sentence returns `sendMessage` to the same chat. The text starts with the headline, holds every tile, and ends with a link whose decoded body `/api/run` accepts and answers with the same headline.
- `/start` lists the demo sentences.
- Text over 600 characters returns 200 with a reply.
- A sticker update returns 200 `{}`.
- A wrong secret returns 403. No secret configured returns 404.

## Known gaps

- Telegram waits about 60 seconds for a webhook. A live NASA POWER point fetch that is slow can run past that. Telegram then retries the same update, and the cache makes the retry fast. The person may wait for the second try.
- `base_url` comes from the request. Behind a proxy that does not forward the scheme, the link starts with `http://` and the deploy redirects it.
