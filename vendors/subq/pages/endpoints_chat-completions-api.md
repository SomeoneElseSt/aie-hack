---
title: Chat Completions API
description: Create OpenAI-compatible chat completions with SubQ.
---

> Status: Early access

Use the Chat Completions API to generate a response from SubQ for a list of conversation messages. These models are early access, enabled per organization. [Request access](https://subq.ai/small#waitlist). For server-managed multi-turn conversations with system instructions and built-in web search, see [Responses API](/endpoints/responses-api/).

```text
POST /v1/chat/completions
```

## Request body

Send a JSON object with the required `model` and `messages` fields. Omit optional fields unless you need to change generation behavior.

| Field              | Type                | Required | Description                                                                                                                             |
| ------------------ | ------------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `model`            | string              | Yes      | Model ID to use, such as `subq-preview`. See [Models](/using-the-api/models/).                                                          |
| `messages`         | array               | Yes      | Conversation messages in order. Must contain at least one message.                                                                      |
| `stream`           | boolean             | No       | When `false` or omitted, returns one JSON response. When `true`, returns server-sent events.                                            |
| `temperature`      | number              | No       | Sampling temperature from `0` to `2`. Higher values make output more random.                                                            |
| `max_tokens`       | integer             | No       | Caps generated tokens. Must be at least `1`. See [Token limits](#token-limits).                                                         |
| `top_p`            | number              | No       | Nucleus sampling value from `0` to `1`. Use this or `temperature`, not both, for most requests.                                         |
| `stop`             | string or string\[] | No       | Stop sequence or sequences where generation should stop.                                                                                |
| `reasoning_effort` | string              | No       | How much internal reasoning the model should use before answering. See [Reasoning effort](#reasoning-effort).                           |
| `response_format`  | object              | No       | Constrain the assistant reply to a JSON Schema. See [Structured outputs](/using-the-api/structured-outputs/).                           |
| `tools`            | array               | No       | Function tools the model may call. See [Function calling](/using-the-api/function-calling/).                                            |
| `tool_choice`      | string or object    | No       | Control whether and which tools the model may call (`"auto"`, `"required"`, `"none"`, or a specific function).                          |
| `store`            | boolean or null     | No       | Set `false` to keep this request and response out of storage. Defaults to `true`. See [Storage](#storage).                              |
| `metadata`         | object or null      | No       | Up to 16 key-value string pairs attached to the request, for your own tracking. Echoed back on the response. See [Metadata](#metadata). |

This page documents the non-streaming response. For a non-streaming request, omit `stream` or set it to `false`.

## Token limits

`max_tokens` caps the tokens generated in the completion. It is a spending limit, not a
response-length limit.

- Applies **only** to generated output—not the prompt.
- **Reasoning is part of that output.** Unless [`reasoning_effort`](#reasoning-effort) is `none`, the model reasons before answering from the same allowance, so a request can return `200 OK` with an empty `content` and `finish_reason` of `"length"`—billed, with nothing visible. A larger `max_tokens` makes this less likely but does not rule it out; `reasoning_effort` of `none` does.
- Input and output share the same [context window](/using-the-api/models/). If `max_tokens` plus the input cannot fit, the API returns `400` with `code` `context_length_exceeded`. Do not set `max_tokens` to the full window.
- Use this parameter exclusively; do not send `max_completion_tokens`.
- If set, the minimum value is 1. If omitted, the response can use all remaining context space.
- If generation hits the cap, `choices[0].finish_reason` is `"length"`.

```json
{
  "model": "subq-preview",
  "messages": [
    {
      "role": "user",
      "content": "In three bullets, explain the difference between indemnification, limitation of liability, and insurance requirements in a software contract."
    }
  ],
  "max_tokens": 500
}
```

```bash title="cURL"
curl --request POST \
  --url https://api.subq.ai/v1/chat/completions \
  --header "Authorization: Bearer $SUBQ_API_KEY" \
  --header 'Content-Type: application/json' \
  --data '
{
  "model": "subq-preview",
  "messages": [
    {
      "role": "user",
      "content": "In three bullets, explain the difference between indemnification, limitation of liability, and insurance requirements in a software contract."
    }
  ],
  "max_tokens": 500
}
'
```

```ts title="TypeScript"
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.SUBQ_API_KEY,
  baseURL: "https://api.subq.ai/v1",
});

const completion = await client.chat.completions.create({
  model: "subq-preview",
  messages: [
    {
      role: "user",
      content: "In three bullets, explain the difference between indemnification, limitation of liability, and insurance requirements in a software contract."
    }
  ],
  max_tokens: 500
});

console.log(completion.choices[0]?.message?.content);
```

```py title="Python"
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
)

completion = client.chat.completions.create(
    model="subq-preview",
    messages=[
        {
            "role": "user",
            "content": "In three bullets, explain the difference between indemnification, limitation of liability, and insurance requirements in a software contract.",
        },
    ],
    max_tokens=500,
)

print(completion.choices[0].message.content)
```

### Detecting a response spent on reasoning

```json
{
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": ""
      },
      "finish_reason": "length"
    }
  ],
  "usage": { "prompt_tokens": 126, "completion_tokens": 64, "total_tokens": 190 }
}
```

Test `message.content` directly—an empty string is easy to pass downstream as if it were
an answer.

```js
const choice = completion.choices[0];

if (choice.finish_reason === "length" && !choice.message.content) {
  // The cap was consumed before the answer began. Retry with
  // reasoning_effort: "none", or with a larger max_tokens.
  // Retrying with the same parameters will produce the same result.
}
```

## Reasoning effort

Set top-level `reasoning_effort` to control how much internal reasoning the model uses before it answers. Possible values are `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, and `max`. Which values are accepted, and what the default is when you omit the field, depends on the model.

- **Reasoning tokens are billed as output tokens.** They are included in `usage.completion_tokens` and counted in `max_tokens`. A one-word classification can bill dozens of times more with reasoning enabled than without.
- **There is no bounded default.** Omitting `reasoning_effort` does not mean light reasoning—the model may reason at length. Set it explicitly on any request with a latency or cost ceiling.

Only `none` gives a guarantee: zero reasoning tokens, even when `max_tokens` is set.

```json
{
  "model": "subq-preview",
  "messages": [
    {
      "role": "user",
      "content": "Classify this transaction dispute into exactly one category: [FRAUD, BILLING, LOAN, TECHNICAL]. Return only the category name.\n\nTicket: 'I see a charge of $45.22 from a gas station in Ohio, but I live in California and haven't traveled all year. Please cancel my card!'"
    }
  ],
  "reasoning_effort": "none"
}
```

```bash title="cURL"
curl --request POST \
  --url https://api.subq.ai/v1/chat/completions \
  --header "Authorization: Bearer $SUBQ_API_KEY" \
  --header 'Content-Type: application/json' \
  --data @- <<'EOF'
{
  "model": "subq-preview",
  "messages": [
    {
      "role": "user",
      "content": "Classify this transaction dispute into exactly one category: [FRAUD, BILLING, LOAN, TECHNICAL]. Return only the category name.\n\nTicket: 'I see a charge of $45.22 from a gas station in Ohio, but I live in California and haven't traveled all year. Please cancel my card!'"
    }
  ],
  "reasoning_effort": "none"
}
EOF
```

```ts title="TypeScript"
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.SUBQ_API_KEY,
  baseURL: "https://api.subq.ai/v1",
});

const completion = await client.chat.completions.create({
  model: "subq-preview",
  messages: [
    {
      role: "user",
      content: "Classify this transaction dispute into exactly one category: [FRAUD, BILLING, LOAN, TECHNICAL]. Return only the category name.\n\nTicket: 'I see a charge of $45.22 from a gas station in Ohio, but I live in California and haven't traveled all year. Please cancel my card!'"
    }
  ],
  reasoning_effort: "none"
});

console.log(completion.choices[0]?.message?.content);
```

```py title="Python"
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
)

completion = client.chat.completions.create(
    model="subq-preview",
    messages=[
        {
            "role": "user",
            "content": "Classify this transaction dispute into exactly one category: [FRAUD, BILLING, LOAN, TECHNICAL]. Return only the category name.\n\nTicket: 'I see a charge of $45.22 from a gas station in Ohio, but I live in California and haven't traveled all year. Please cancel my card!'",
        },
    ],
    reasoning_effort="none",
)

print(completion.choices[0].message.content)
```

### Choosing a value

Effort selects a reasoning strategy, not a token budget: higher effort does not reliably
mean more tokens, and the relationship differs by prompt and by model version. Benchmark
the candidates on your own prompts rather than assuming an ordering.

| Workload                                           | Suggested effort                  |
| -------------------------------------------------- | --------------------------------- |
| Classification, routing, extraction, short answers | `none`                            |
| Open-ended analysis and multi-step work            | `medium` or `high`; compare both  |
| Tight `max_tokens`                                 | `none`, or expect empty `content` |

For classification and routing with probabilities, use the [Decisions API](/endpoints/decisions-api/).

## Messages

Each message has a `role` and `content`.

| Field     | Type                      | Required | Description                                                   |
| --------- | ------------------------- | -------- | ------------------------------------------------------------- |
| `role`    | string                    | Yes      | One of `system`, `user`, `assistant`, or `tool`.              |
| `content` | string or content part\[] | Yes      | Message text as a plain string, or an array of content parts. |

Use `system` for durable instructions, `user` for user input, `assistant` for prior model responses (including messages that contain `tool_calls`), and `tool` for tool result messages already produced by your application. See [Function calling](/using-the-api/function-calling/).

The simplest content shape is a string:

```json
{
  "role": "user",
  "content": "Summarize this release note."
}
```

You can also send text content parts:

```json
{
  "role": "user",
  "content": [
    { "type": "text", "text": "Summarize this release note." }
  ]
}
```

For document input, send a text instruction and one or more `file` parts in the same `user` message:

```json
{
  "role": "user",
  "content": [
    { "type": "text", "text": "Summarize these documents." },
    {
      "type": "file",
      "filename": "financial-report-2026.pdf",
      "mime_type": "application/pdf",
      "file_data": "JVBERi0xLjcKJdDUxdgK..."
    },
    {
      "type": "file",
      "filename": "meeting-notes.txt",
      "mime_type": "text/plain",
      "file_data": "U3ViUSBkb2N1bWVudCBub3Rlcy4uLg=="
    }
  ]
}
```

Document file parts accept inline base64 (`file_data`) or an uploaded `file_id`. Image, audio, video, URL-based file inputs, and other content part types are rejected. A photo goes to the [Decisions API](/endpoints/decisions-api/#images). See [Sending files](/using-the-api/file-inputs/) for file part examples. For the Responses API, use `input_file` with `file_id` instead — see [Uploaded files](/endpoints/responses-api/#uploaded-files-file_id).

### Uploaded files (`file_id`)

Upload the document with the [Files API](/endpoints/files-api/), wait until
`status` is `processed`, then pass its id on a `file` part:

```json
{
  "model": "subq-preview",
  "messages": [{
    "role": "user",
    "content": [
      { "type": "text", "text": "Summarize this report." },
      { "type": "file", "file_id": "file_abc123" }
    ]
  }]
}
```

An unknown id, or a file owned by another organization, returns `404`
`file_not_found`. A file that hasn't finished processing returns `409`
`file_not_ready`; retry once `status` is `processed`. See
[Sending files](/using-the-api/file-inputs/#uploaded-files) for SDK examples.

## Metadata

Attach up to 16 key-value string pairs to a request for your own tracking — run IDs, experiment names, customer tags. SubQ does not interpret or act on these values.

- Keys can be at most 64 characters; values at most 512 characters.
- Values must be strings. Numbers and booleans are coerced to strings; objects, arrays, and other non-string values are rejected with a `400` `validation_error`.
- Omit `metadata`, or pass `null` or `{}`, for no metadata — all three are treated the same.

```json
{
  "model": "subq-preview",
  "messages": [{ "role": "user", "content": "Summarize this release note." }],
  "metadata": { "run_id": "eval-2026-08-31-014", "experiment": "reasoning-ablation" }
}
```

A non-streaming response echoes `metadata` back verbatim:

```json
{
  "id": "chatcmpl-e1395060-5a57-4182-a833-c5a208137f70",
  "metadata": { "run_id": "eval-2026-08-31-014", "experiment": "reasoning-ablation" }
}
```

Streaming chunks do not include `metadata`. `metadata` is never forwarded to the underlying model — it is for your own request tracking only.

## Storage

By default SubQ stores each request and response under the [data-retention policy](/using-the-api/data-retention/). Set `store: false` to keep a single request, including any inline files, out of storage:

```json
{
  "model": "subq-preview",
  "messages": [{ "role": "user", "content": "Summarize this patient intake note." }],
  "store": false
}
```

Files you reference by `file_id` stay available. To control exactly when a
document is deleted, upload it with the [Files API](/endpoints/files-api/), pass
its `file_id`, and [delete the file](/endpoints/files-api/#delete-file) when
you're done.

## Request examples

Use cURL for direct HTTP calls, or use the official OpenAI SDK with SubQ's base URL.

```bash title="cURL"
curl --request POST \
  --url https://api.subq.ai/v1/chat/completions \
  --header "Authorization: Bearer $SUBQ_API_KEY" \
  --header 'Content-Type: application/json' \
  --data '
{
  "model": "subq-preview",
  "messages": [
    {
      "role": "system",
      "content": "You are concise and practical."
    },
    {
      "role": "user",
      "content": "In three bullets, explain the difference between indemnification, limitation of liability, and insurance requirements in a software contract."
    }
  ],
  "temperature": 0.2,
  "max_tokens": 500
}
'
```

```ts title="TypeScript"
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.SUBQ_API_KEY,
  baseURL: "https://api.subq.ai/v1",
});

const completion = await client.chat.completions.create({
  model: "subq-preview",
  messages: [
    {
      role: "system",
      content: "You are concise and practical."
    },
    {
      role: "user",
      content: "In three bullets, explain the difference between indemnification, limitation of liability, and insurance requirements in a software contract."
    }
  ],
  temperature: 0.2,
  max_tokens: 500
});

console.log(completion.choices[0]?.message?.content);
```

```py title="Python"
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
)

completion = client.chat.completions.create(
    model="subq-preview",
    messages=[
        {
            "role": "system",
            "content": "You are concise and practical.",
        },
        {
            "role": "user",
            "content": "In three bullets, explain the difference between indemnification, limitation of liability, and insurance requirements in a software contract.",
        },
    ],
    temperature=0.2,
    max_tokens=500,
)

print(completion.choices[0].message.content)
```

## Response

A non-streaming request returns a JSON object with the OpenAI-compatible chat completion shape.

```json {10-13}
{
  "id": "chatcmpl-e1395060-5a57-4182-a833-c5a208137f70",
  "object": "chat.completion",
  "created": 1784314379,
  "model": "subq-preview",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "*   **Indemnification** is a contractual obligation where one party agrees to compensate the other for losses, damages, or legal costs arising from third-party claims (such as intellectual property infringement or data breaches), effectively shifting the financial risk of those specific external liabilities to the responsible party.\n*   **Limitation of Liability** caps the maximum amount of damages one party can be forced to pay the other for breach of contract or negligence, often excluding consequential or indirect damages, thereby protecting both sides from catastrophic financial exposure beyond a predefined threshold (e.g., fees paid in the prior 12 months).\n*   **Insurance Requirements** mandate that one or both parties maintain specific types and minimum amounts of insurance coverage (such as general liability, professional liability, or cyber insurance) to ensure there are financial resources available to cover potential claims, serving as a verification of financial capacity rather than a direct transfer of risk between the contracting parties."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 110,
    "completion_tokens": 188,
    "total_tokens": 298
  }
}
```

### Response fields

| Field      | Type    | Description                                                                                                         |
| ---------- | ------- | ------------------------------------------------------------------------------------------------------------------- |
| `id`       | string  | Unique completion ID.                                                                                               |
| `object`   | string  | Object type. Non-streaming responses use `chat.completion`.                                                         |
| `created`  | integer | Unix timestamp, in seconds, for when the completion was created.                                                    |
| `model`    | string  | Model ID used for the completion.                                                                                   |
| `choices`  | array   | Generated choices. SubQ returns at least one choice for a successful request.                                       |
| `usage`    | object  | Token usage for the request.                                                                                        |
| `metadata` | object  | Echo of the request's `metadata`, or `{}` if none was sent. Omitted on streaming chunks. See [Metadata](#metadata). |

### Choice fields

| Field                | Type    | Description                                                                                                                                                                    |
| -------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `index`              | integer | Choice index.                                                                                                                                                                  |
| `message.role`       | string  | Role of the returned message, usually `assistant`.                                                                                                                             |
| `message.content`    | string  | Generated text. May be `null` when the model returns tool calls, and an empty string when `max_tokens` was consumed before the answer began—see [Token limits](#token-limits). |
| `message.tool_calls` | array   | Present when the model requests function calls. See [Function calling](/using-the-api/function-calling/).                                                                      |
| `finish_reason`      | string  | Reason generation stopped. Common values include `stop`, `length` (hit `max_tokens` or the remaining window), and `tool_calls`. Handle unknown string values defensively.      |

### Usage fields

| Field               | Type    | Description                                                                                  |
| ------------------- | ------- | -------------------------------------------------------------------------------------------- |
| `prompt_tokens`     | integer | Tokens counted from the request messages.                                                    |
| `completion_tokens` | integer | Tokens generated in the response, including any reasoning tokens. Billed at the output rate. |
| `total_tokens`      | integer | Sum of prompt and completion tokens.                                                         |

`completion_tokens` can be entirely reasoning with nothing visible in `content` — test `message.content` directly rather than inferring from token counts.
