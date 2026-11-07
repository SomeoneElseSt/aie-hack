---
title: API overview
description: How SubQ's OpenAI-compatible API fits into a developer integration.
---

SubQ serves two model families, each on its own endpoints:

- **SubQ Snap** (`subq-snap-1.1`) (Public preview)
  returns typed decisions about text and images on the
  [Decisions API](/endpoints/decisions-api/). Available to every account.
- **SubQ Preview** (`subq-preview`) (Early access)
  generates text on [Chat Completions](/endpoints/chat-completions-api/) and
  [Responses](/endpoints/responses-api/), both OpenAI-compatible.
  [Request access](https://subq.ai/small#waitlist).

The [Files](/endpoints/files-api/), [Conversations](/endpoints/conversations-api/),
and [Models](/endpoints/models-api/) endpoints support them. See
[Models](/using-the-api/models/) for what each model accepts.

## Request flow

1. Create an account at [console.subq.ai](https://console.subq.ai)
2. Generate an API key from the console
3. Set the SubQ base URL in your HTTP client or OpenAI SDK
4. Choose an endpoint and send a request using a [SubQ model](/using-the-api/models/).
5. Enable streaming on Chat Completions or Responses when your product needs tokens as they are generated

## Base URL

Send API requests to:

```
https://api.subq.ai/v1
```

Treat each endpoint page as the contract for its supported models, fields, and
response formats.

## Endpoints

| Endpoint                                             | Method                    | Path                   | Model                         | Use it to                                                                                                                               |
| ---------------------------------------------------- | ------------------------- | ---------------------- | ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| [Models](/endpoints/models-api/)                     | `GET`                     | `/v1/models`           | —                             | List the model IDs available to your API key at runtime.                                                                                |
| [Decisions](/endpoints/decisions-api/)               | `POST`                    | `/v1/systemone`        | `subq-snap-1.1`               | Return typed yes/no, choice, and score decisions about text or images, with probabilities and confidence.                               |
| [Responses](/endpoints/responses-api/)               | `POST`                    | `/v1/responses`        | `subq-preview` (Early access) | Run multi-turn and long-context workflows with `instructions`, built-in web search, and server-side history via `previous_response_id`. |
| [Chat Completions](/endpoints/chat-completions-api/) | `POST`                    | `/v1/chat/completions` | `subq-preview` (Early access) | Generate text from `messages`, statelessly. The drop-in path for OpenAI migrations.                                                     |
| [Files](/endpoints/files-api/)                       | `POST` / `GET` / `DELETE` | `/v1/files`            | Used with `subq-preview`      | Upload documents once and reference them by `file_id` in Chat Completions or Responses.                                                 |
| [Conversations](/endpoints/conversations-api/)       | `POST` / `GET` / `DELETE` | `/v1/conversations`    | Used with `subq-preview`      | Create, inspect, retag, and delete a conversation's history, independent of any single turn.                                            |

## Next steps

- Use the [Quickstart](/) to verify your API key.
- Read [Authentication](/using-the-api/authentication/) before wiring credentials into an app.
- Review SubQ capabilities in [Models](/using-the-api/models/).
- Return typed decisions with the [Decisions API](/endpoints/decisions-api/).
- Put documents in a prompt with [Sending files](/using-the-api/file-inputs/).
- Return schema-constrained JSON with [Structured outputs](/using-the-api/structured-outputs/).
- Connect models to your app with [Function calling](/using-the-api/function-calling/).
- Check [Data retention](/using-the-api/data-retention/) for how long SubQ stores your prompts and completions.
