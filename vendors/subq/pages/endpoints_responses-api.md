---
title: Responses API
description: Stateful inference with system instructions, web search, and server-managed conversation history.
---

> Status: Early access

Use the Responses API for stateful inference. These models are early access, enabled per organization. [Request access](https://subq.ai/small#waitlist). SubQ stores each turn server-side and links them by ID, so multi-turn workflows — long document review, case research, and agent loops — need no client-side history management. Pass `previous_response_id` to continue from a prior turn.

For stateless requests where you send the full `messages` array each time, use the [Chat Completions API](/endpoints/chat-completions-api/).

```text
POST /v1/responses
```

## When to use which endpoint

|                     | Chat Completions                                                                                                | Responses API                                                                                 |
| ------------------- | --------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Conversation state  | You send full `messages[]` each request                                                                         | Server stores history; continue with `previous_response_id` or `conversation`                 |
| Best for            | Drop-in OpenAI migrations, custom message assembly                                                              | Multi-turn apps, long-context workflows, simpler clients                                      |
| System prompt       | `system` role in messages                                                                                       | `instructions` (per-turn; not inherited)                                                      |
| Built-in web search | Not available                                                                                                   | `tools: [{ "type": "web_search_preview" }]`                                                   |
| Function calling    | Nested shape (`{"type":"function","function":{...}}`), see [Function calling](/using-the-api/function-calling/) | Flattened shape (`{"type":"function","name":...}`), see [Function calling](#function-calling) |
| Structured Outputs  | `response_format`                                                                                               | `text.format` (flattened shape)                                                               |
| File input          | `file` parts (`file_data` or `file_id`)                                                                         | `input_file` parts (`file_id` only)                                                           |
| Reasoning effort    | Top-level `reasoning_effort`                                                                                    | Nested `reasoning.effort`                                                                     |
| Stream terminator   | `data: [DONE]`                                                                                                  | `response.completed` event                                                                    |

## Request body

| Field                  | Type                      | Required | Description                                                                                                                                                                                                                                                         |
| ---------------------- | ------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `model`                | string                    | Yes      | Model ID to use, such as `subq-preview`. See [Models](/using-the-api/models/).                                                                                                                                                                                      |
| `input`                | string or content part\[] | Yes      | The user's message for this turn. A plain string, or an array of `input_text` and `input_file` parts. See [Input](#input).                                                                                                                                          |
| `instructions`         | string or null            | No       | System prompt for the current turn only. Not inherited — pass it on every request if it must persist.                                                                                                                                                               |
| `previous_response_id` | string or null            | No       | Continues from a specific prior response. Mutually exclusive with `conversation`. Omit or pass `null` to start a new one. Returns `404` if the ID does not exist.                                                                                                   |
| `conversation`         | string or null            | No       | Continues a conversation by its `conv_...` id, picking up from its most recently written turn. Mutually exclusive with `previous_response_id`. See [Multi-turn conversations](#multi-turn-conversations). Returns `404` if the conversation does not exist.         |
| `tools`                | object\[] or null         | No       | Tools available to the model: built-in tools SubQ executes server-side (`{ "type": "web_search_preview" }`, see [Web search](#web-search)) and function tools your application executes (`{ "type": "function", ... }`, see [Function calling](#function-calling)). |
| `reasoning`            | object or null            | No       | Reasoning configuration for this turn. Set `effort` to control how much internal reasoning the model uses. See [Reasoning effort](#reasoning-effort).                                                                                                               |
| `stream`               | boolean                   | No       | When `false` or omitted, returns one JSON response. When `true`, returns server-sent events.                                                                                                                                                                        |
| `text`                 | object or null            | No       | Output format. Defaults to `{ "format": { "type": "text" } }`. See [Structured outputs](#structured-outputs).                                                                                                                                                       |
| `store`                | boolean or null           | No       | Set `false` to run this turn without saving it. Defaults to `true`. See [Storage](#storage).                                                                                                                                                                        |
| `metadata`             | object or null            | No       | Up to 16 key-value string pairs attached to the request, for your own tracking. Echoed back on the response, including streaming `response.created`/`response.completed` events. See [Metadata](#metadata).                                                         |

## Reasoning effort

Pass a `reasoning` object with an `effort` field — not a boolean. Possible `effort` values are `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, and `max`. Which values are accepted, and what the default is when you omit `reasoning`, depends on the model.

This is the Responses equivalent of Chat Completions `reasoning_effort`. SubQ forwards the selected effort to the upstream model.

- **Reasoning tokens are billed as output tokens.** They are included in `usage.output_tokens`. A short answer can bill dozens of times more with reasoning enabled than without.
- **There is no bounded default.** Omitting `reasoning` does not mean light reasoning—the model may reason at length. Set it explicitly on any request with a latency or cost ceiling.

Only `none` gives a guarantee: zero reasoning tokens.

```json
{
  "model": "subq-preview",
  "instructions": "You are a legal research assistant. Use plain language. Cite only facts in the conversation.",
  "input": "Summarize the major self-preferencing antitrust cases since 2010 and list open questions for counsel.",
  "reasoning": {
    "effort": "high"
  }
}
```

```bash title="cURL"
curl --request POST \
  --url https://api.subq.ai/v1/responses \
  --header "Authorization: Bearer $SUBQ_API_KEY" \
  --header 'Content-Type: application/json' \
  --data '
{
  "model": "subq-preview",
  "instructions": "You are a legal research assistant. Use plain language. Cite only facts in the conversation.",
  "input": "Summarize the major self-preferencing antitrust cases since 2010 and list open questions for counsel.",
  "reasoning": {
    "effort": "high"
  }
}
'
```

```ts title="TypeScript"
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.SUBQ_API_KEY,
  baseURL: "https://api.subq.ai/v1",
});

const response = await client.responses.create({
  model: "subq-preview",
  instructions: "You are a legal research assistant. Use plain language. Cite only facts in the conversation.",
  input: "Summarize the major self-preferencing antitrust cases since 2010 and list open questions for counsel.",
  reasoning: {
    effort: "high"
  }
});

console.log(response.output[0].content[0].text);
```

```py title="Python"
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
)

response = client.responses.create(
    model="subq-preview",
    instructions="You are a legal research assistant. Use plain language. Cite only facts in the conversation.",
    input="Summarize the major self-preferencing antitrust cases since 2010 and list open questions for counsel.",
    reasoning={
        "effort": "high",
    },
)

print(response.output[0].content[0].text)
```

### Choosing a value

Effort selects a reasoning strategy, not a token budget: higher effort does not reliably
mean more tokens, and the relationship differs by prompt and by model version. Benchmark
the candidates on your own prompts rather than assuming an ordering.

| Workload                                           | Suggested effort                 |
| -------------------------------------------------- | -------------------------------- |
| Classification, routing, extraction, short answers | `none`                           |
| Open-ended analysis and multi-step work            | `medium` or `high`; compare both |

## Input

Set `input` to a plain string:

```json
{
  "input": "Summarize the major self-preferencing antitrust cases since 2010."
}
```

A content-part array is also accepted. SubQ processes `input_text` (user text) and `input_file` (an uploaded file referenced by `file_id`). Image parts are ignored. A photo goes to the [Decisions API](/endpoints/decisions-api/#images). Prefer the string form when the turn has no files.

For large documents, include the text in `input` (or earlier turns) and use SubQ's long context window, or upload the file and pass its `file_id`.

### Uploaded files (`file_id`)

Upload the document with the [Files API](/endpoints/files-api/), wait until `status` is `processed`, then send an `input_file` part. Responses uses OpenAI's `input_file` type — not the Chat Completions `file` part.

```json
{
  "model": "subq-preview",
  "input": [
    { "type": "input_file", "file_id": "file_abc123" },
    { "type": "input_text", "text": "Summarize this document." }
  ]
}
```

```bash title="cURL"
curl --request POST \
  --url https://api.subq.ai/v1/responses \
  --header "Authorization: Bearer $SUBQ_API_KEY" \
  --header 'Content-Type: application/json' \
  --data '
{
  "model": "subq-preview",
  "input": [
    {
      "type": "input_file",
      "file_id": "file_abc123"
    },
    {
      "type": "input_text",
      "text": "Summarize this document."
    }
  ]
}
'
```

```ts title="TypeScript"
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.SUBQ_API_KEY,
  baseURL: "https://api.subq.ai/v1",
});

const response = await client.responses.create({
  model: "subq-preview",
  input: [
    {
      type: "input_file",
      file_id: "file_abc123"
    },
    {
      type: "input_text",
      text: "Summarize this document."
    }
  ]
});

console.log(response.output[0].content[0].text);
```

```py title="Python"
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
)

response = client.responses.create(
    model="subq-preview",
    input=[
        {
            "type": "input_file",
            "file_id": "file_abc123",
        },
        {
            "type": "input_text",
            "text": "Summarize this document.",
        },
    ],
)

print(response.output[0].content[0].text)
```

| Field     | Type   | Required | Description                                   |
| --------- | ------ | -------- | --------------------------------------------- |
| `type`    | string | Yes      | Must be `"input_file"`.                       |
| `file_id` | string | Yes      | File identifier returned by `POST /v1/files`. |

Inline `file_data` is not accepted on Responses. Upload the file and pass `file_id`, or use [Chat Completions](/endpoints/chat-completions-api/) for a one-off base64 request. A missing `file_id` returns `400` `validation_error`. An unknown id, or a file owned by another organization, returns `404` `file_not_found`.

You can also wrap parts in a message item (`{ "role": "user", "content": [ ... ] }`), which is the shape the OpenAI SDK sends. See [Sending files](/using-the-api/file-inputs/) for upload vs inline, accepted formats, and the Chat Completions part shape.

## Instructions

Use `instructions` for system guidance — policy constraints, role, citation rules, or output style. It is inserted before conversation history for the current turn, equivalent to a Chat Completions `system` message.

`instructions` are **not** carried by `previous_response_id`. Resend them on every turn that needs the same system prompt.

```json
{
  "model": "subq-preview",
  "instructions": "You are a legal research assistant. Use plain language. Cite only facts in the conversation.",
  "input": "Summarize the major self-preferencing antitrust cases since 2010 and list open questions for counsel."
}
```

## Web search

Enable built-in web search with a single tool marker. The proxy runs an agentic loop server-side: when the model asks to search, SubQ executes the search, feeds results back, and continues until a final answer — within one request.

```json
{
  "model": "subq-preview",
  "instructions": "Be concise (3 bullets max). Prefer Fed, FDIC, and OCC releases from today. If nothing material, say so.",
  "input": "Any material US bank regulatory news today?",
  "tools": [{ "type": "web_search_preview" }]
}
```

```bash title="cURL"
curl --request POST \
  --url https://api.subq.ai/v1/responses \
  --header "Authorization: Bearer $SUBQ_API_KEY" \
  --header 'Content-Type: application/json' \
  --data '
{
  "model": "subq-preview",
  "instructions": "Be concise (3 bullets max). Prefer Fed, FDIC, and OCC releases from today. If nothing material, say so.",
  "input": "Any material US bank regulatory news today?",
  "tools": [
    {
      "type": "web_search_preview"
    }
  ]
}
'
```

```ts title="TypeScript"
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.SUBQ_API_KEY,
  baseURL: "https://api.subq.ai/v1",
});

const response = await client.responses.create({
  model: "subq-preview",
  instructions: "Be concise (3 bullets max). Prefer Fed, FDIC, and OCC releases from today. If nothing material, say so.",
  input: "Any material US bank regulatory news today?",
  tools: [
    {
      type: "web_search_preview"
    }
  ]
});

console.log(response.output[0].content[0].text);
```

```py title="Python"
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
)

response = client.responses.create(
    model="subq-preview",
    instructions="Be concise (3 bullets max). Prefer Fed, FDIC, and OCC releases from today. If nothing material, say so.",
    input="Any material US bank regulatory news today?",
    tools=[
        {
            "type": "web_search_preview",
        },
    ],
)

print(response.output[0].content[0].text)
```

### Prompting the model to search

Adding `web_search_preview` enables web search, but `tool_choice` remains `auto`. If you want the model to search rather than rely on its internal knowledge, update your instructions to explicitly tell it to:

- Search the web before answering.
- Verify facts against current sources.

```json
{
  "model": "subq-preview",
  "instructions": "You must search the web before answering. Verify each case's latest procedural status using current authoritative sources. Prefer court decisions and regulator publications.",
  "input": "Summarize the major self-preferencing antitrust cases since 2010 and list open questions for counsel.",
  "tools": [{ "type": "web_search_preview" }]
}
```

Avoid instructions such as “cite only facts in the conversation” when you want current web results, because they may discourage the model from relying on retrieved information.

Each executed search appears in `output` as a `web_search_call` item, in the order it ran, followed by the final assistant `message`. The model may also emit a short text `message` *before* it searches (see [Text preamble before tool calls](#text-preamble-before-tool-calls)), so a turn can contain two `message` items: `[message, web_search_call, message]`.

```jsonc
{
  "output": [
    {
      "id": "ws_019f5c714e4479a5a37680c82da9d06c",
      "type": "web_search_call",
      "status": "completed",
      "action": {
        "type": "search",
        "queries": [
          "US bank regulatory news today",
          "FDIC announcements today",
          "OCC regulatory updates today",
          "Federal Reserve banking regulations today"
        ],
        "query": "US bank regulatory news today"
      }
    },
    {
      "id": "msg_019f5c71d7b37b0695ca49dc05c81ba1",
      "type": "message",
      "status": "completed",
      "role": "assistant",
      "phase": "final_answer",
      "content": [
        {
          "type": "output_text",
          "annotations": [],
          "logprobs": [],
          "text": "Based on today's regulatory developments, here are the key updates affecting US banks:\n\n- **Immigrant Lending Guidance**: The OCC, FDIC, and NCUA jointly issued nonbinding guidance warning banks about credit risks when lending to undocumented immigrants, citing potential income instability and deportation risks. This implements a May 2026 Trump executive order and follows FinCEN's May advisory on identity theft and money laundering red flags.\n\n- **Circle National Trust Approval**: The OCC granted final approval for Circle to establish a federally regulated national trust bank (Circle National Trust) for digital asset custody. This allows Circle to manage USDC stablecoin reserves under federal oversight, marking a significant step in crypto regulation.\n\n- **Bank Failure**: The OCC shuttered Kentland Federal Savings and Loan Association (Indiana), the nation's smallest standalone bank, due to critical undercapitalization from unsafe practices. This is the third bank failure in 2026."
        }
      ]
    }
  ]
}
```

**Production notes:**

- `tool_choice` is `auto` — the model searches only when needed.
- A single `web_search_call` may carry up to 5 queries (`action.queries`), run concurrently; `action.query` mirrors the first.
- Searches and answers are stored and replayed on later `previous_response_id` turns.
- Works with streaming and non-streaming. `usage` covers every inference round in the loop.
- Don't assume the answer is `output[0]` or the only `message` item — select `output` items by `type`, and if more than one `message` is present, the **last** one is the final answer. See [Extracting the assistant text](#extracting-the-assistant-text).

## Function calling

Define a function tool with the flattened Responses API shape — `type`, `name`, `description`, `parameters`, and `strict` sit directly on the tool object (unlike Chat Completions, which nests these under a `function` object). See [Function calling](/using-the-api/function-calling/) for the concept, the tool calling flow, and the Chat Completions comparison.

```json
{
  "model": "subq-preview",
  "input": "What are NVDA and MSFT trading at, and which moved more today?",
  "tools": [
    {
      "type": "function",
      "name": "get_stock_quote",
      "description": "Get the latest price for one stock ticker. Returns symbol, price, change_percent, and as_of.",
      "parameters": {
        "type": "object",
        "properties": {
          "symbol": {
            "type": "string",
            "description": "Ticker symbol, e.g. NVDA or MSFT."
          }
        },
        "required": ["symbol"],
        "additionalProperties": false
      },
      "strict": true
    }
  ]
}
```

```bash title="cURL"
curl --request POST \
  --url https://api.subq.ai/v1/responses \
  --header "Authorization: Bearer $SUBQ_API_KEY" \
  --header 'Content-Type: application/json' \
  --data '
{
  "model": "subq-preview",
  "input": "What are NVDA and MSFT trading at, and which moved more today?",
  "tools": [
    {
      "type": "function",
      "name": "get_stock_quote",
      "description": "Get the latest price for one stock ticker. Returns symbol, price, change_percent, and as_of.",
      "parameters": {
        "type": "object",
        "properties": {
          "symbol": {
            "type": "string",
            "description": "Ticker symbol, e.g. NVDA or MSFT."
          }
        },
        "required": [
          "symbol"
        ],
        "additionalProperties": false
      },
      "strict": true
    }
  ]
}
'
```

```ts title="TypeScript"
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.SUBQ_API_KEY,
  baseURL: "https://api.subq.ai/v1",
});

const response = await client.responses.create({
  model: "subq-preview",
  input: "What are NVDA and MSFT trading at, and which moved more today?",
  tools: [
    {
      type: "function",
      name: "get_stock_quote",
      description: "Get the latest price for one stock ticker. Returns symbol, price, change_percent, and as_of.",
      parameters: {
        type: "object",
        properties: {
          symbol: {
            type: "string",
            description: "Ticker symbol, e.g. NVDA or MSFT."
          }
        },
        required: [
          "symbol"
        ],
        additionalProperties: false
      },
      strict: true
    }
  ]
});

console.log(response.output[0].content[0].text);
```

```py title="Python"
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
)

response = client.responses.create(
    model="subq-preview",
    input="What are NVDA and MSFT trading at, and which moved more today?",
    tools=[
        {
            "type": "function",
            "name": "get_stock_quote",
            "description": "Get the latest price for one stock ticker. Returns symbol, price, change_percent, and as_of.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Ticker symbol, e.g. NVDA or MSFT.",
                    },
                },
                "required": [
                    "symbol",
                ],
                "additionalProperties": False,
            },
            "strict": True,
        },
    ],
)

print(response.output[0].content[0].text)
```

When the model calls a function, the response contains a `function_call` output item — one per call, since the model may call the same function (or several different ones) in parallel within a single turn:

```json
{
  "id": "resp_01a3f8c2...",
  "output": [
    {
      "id": "fc_01a3f8c2b9d14e67a8b5c3d0e2f14a79",
      "type": "function_call",
      "status": "completed",
      "call_id": "chatcmpl-tool-3f9a7c1e6b2d4508",
      "name": "get_stock_quote",
      "arguments": "{\"symbol\": \"NVDA\"}"
    },
    {
      "id": "fc_01a3f8c2b9d14e67a8b5c3d0e2f14a80",
      "type": "function_call",
      "status": "completed",
      "call_id": "chatcmpl-tool-3f9a7c1e6b2d4509",
      "name": "get_stock_quote",
      "arguments": "{\"symbol\": \"MSFT\"}"
    }
  ]
}
```

`call_id` doesn't always share the `resp_`/`fc_` prefix style — treat it as an opaque string and pass it back verbatim in `function_call_output`.

> **Optional text preamble.** The model may emit a short text message before its tool calls. See [Text preamble before tool calls](#text-preamble-before-tool-calls) below for the exact ordering.

Execute the function in your application, then send its result back as a `function_call_output`. Include one function call output per `call_id`:

```json
{
  "model": "subq-preview",
  "previous_response_id": "resp_01a3f8c2...",
  "input": [
    {
      "type": "function_call_output",
      "call_id": "chatcmpl-tool-3f9a7c1e6b2d4508",
      "output": "{\"symbol\":\"NVDA\",\"price\":210.96,\"change_percent\":4.03,\"as_of\":\"2026-07-17T17:42:03.000Z\"}"
    },
    {
      "type": "function_call_output",
      "call_id": "chatcmpl-tool-3f9a7c1e6b2d4509",
      "output": "{\"symbol\":\"MSFT\",\"price\":402.18,\"change_percent\":1.12,\"as_of\":\"2026-07-17T17:42:03.000Z\"}"
    }
  ],
  "tools": [{ "type": "function", "name": "get_stock_quote", "description": "...", "parameters": { "type": "object", "properties": {} } }]
}
```

The proxy replays the function call and function call output into model context. The next response may contain a final response or another `function_call`; repeat the tool calling flow until the model returns a message. Resend `tools` on each request where the model should be allowed to make another call. Function call outputs are accepted only for calls from the immediately preceding `previous_response_id`.

### Full loop

A response can contain more function calls after receiving function call outputs, so keep looping until the model returns a final response — cap the number of rounds to avoid runaway loops. Execute every `function_call` in a turn (the model may call in parallel) with `Promise.all`, and use the last `message` item to surface any text preamble to the user while functions run:

```ts title="TypeScript"
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.SUBQ_API_KEY,
  baseURL: "https://api.subq.ai/v1",
});

// Responses API function tools use a flattened shape. Unlike Chat
// Completions, name/description/parameters are not nested under `function`.
const tools = [
  {
    type: "function",
    name: "get_stock_quote",
    description:
      "Get the latest price for one stock ticker. Returns symbol, price, change_percent, and as_of.",
    parameters: {
      type: "object",
      properties: {
        symbol: {
          type: "string",
          description: "Ticker symbol, e.g. NVDA or MSFT.",
        },
      },
      required: ["symbol"],
      additionalProperties: false,
    },
    strict: true,
  },
];

const SAMPLE_QUOTES = {
  NVDA: { price: 210.96, change_percent: 4.03 },
  MSFT: { price: 402.18, change_percent: 1.12 },
};

// Replace this stub with a call to your market-data provider.
async function getStockQuote({ symbol }) {
  return { symbol, as_of: new Date().toISOString(), ...SAMPLE_QUOTES[symbol] };
}

const functionHandlers = {
  get_stock_quote: getStockQuote,
};

// A function_call turn may carry a text preamble as a `message` item before
// the call (see "Text preamble before tool calls"); it is never the final
// answer by itself, so always take the *last* message item.
function getLastAssistantText(response) {
  const messages = response.output.filter((item) => item.type === "message");

  return (
    messages
      .at(-1)
      ?.content?.filter((part) => part.type === "output_text")
      .map((part) => part.text)
      .join("") ?? ""
  );
}

let response = await client.responses.create({
  model: "subq-preview",
  input: "What are NVDA and MSFT trading at, and which moved more today?",
  tools,
});

// A response can contain more function calls after receiving function call
// outputs, so continue until the model returns a final response.
const maxFunctionRounds = 8;

for (let round = 0; round < maxFunctionRounds; round += 1) {
  const functionCalls = response.output.filter(
    (item) => item.type === "function_call",
  );

  if (functionCalls.length === 0) break;

  // A message before a function call is an optional preamble, not the final
  // answer. It can be shown to the user while the functions are running.
  const preamble = getLastAssistantText(response);
  if (preamble) {
    console.log(preamble);
  }

  // Execute every function_call in the turn — the model may call in parallel.
  const functionCallOutputs = await Promise.all(
    functionCalls.map(async (call) => {
      const handler = functionHandlers[call.name];
      if (!handler) {
        throw new Error(`No handler registered for function "${call.name}".`);
      }

      return {
        type: "function_call_output",
        call_id: call.call_id,
        output: JSON.stringify(await handler(JSON.parse(call.arguments))),
      };
    }),
  );

  response = await client.responses.create({
    model: "subq-preview",
    previous_response_id: response.id,
    input: functionCallOutputs,
    // Resend tools so the model can request another function call.
    tools,
  });
}

if (response.output.some((item) => item.type === "function_call")) {
  throw new Error(`Exceeded ${maxFunctionRounds} function-calling rounds.`);
}

console.log(getLastAssistantText(response));
```

```py title="Python"
import json
import os
from datetime import datetime, timezone

from openai import OpenAI

client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
)

# Responses API function tools use a flattened shape. Unlike Chat
# Completions, name/description/parameters are not nested under `function`.
tools = [
    {
        "type": "function",
        "name": "get_stock_quote",
        "description": (
            "Get the latest price for one stock ticker. "
            "Returns symbol, price, change_percent, and as_of."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Ticker symbol, e.g. NVDA or MSFT.",
                },
            },
            "required": ["symbol"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]

SAMPLE_QUOTES = {
    "NVDA": {"price": 210.96, "change_percent": 4.03},
    "MSFT": {"price": 402.18, "change_percent": 1.12},
}


# Replace this stub with a call to your market-data provider.
def get_stock_quote(symbol):
    quote = SAMPLE_QUOTES.get(symbol, {})
    return {
        "symbol": symbol,
        "as_of": datetime.now(timezone.utc).isoformat(),
        **quote,
    }


function_handlers = {
    "get_stock_quote": get_stock_quote,
}


# A function_call turn may carry a text preamble as a `message` item before
# the call (see "Text preamble before tool calls"); it is never the final
# answer by itself, so always take the *last* message item.
def get_last_assistant_text(response):
    messages = [item for item in response.output if item.type == "message"]
    if not messages:
        return ""
    return "".join(
        part.text
        for part in (messages[-1].content or [])
        if part.type == "output_text"
    )


response = client.responses.create(
    model="subq-preview",
    input="What are NVDA and MSFT trading at, and which moved more today?",
    tools=tools,
)

# A response can contain more function calls after receiving function call
# outputs, so continue until the model returns a final response.
max_function_rounds = 8

for _ in range(max_function_rounds):
    function_calls = [
        item for item in response.output if item.type == "function_call"
    ]

    if not function_calls:
        break

    # A message before a function call is an optional preamble, not the final
    # answer. It can be shown to the user while the functions are running.
    preamble = get_last_assistant_text(response)
    if preamble:
        print(preamble)

    # Execute every function_call in the turn — the model may call in parallel.
    function_call_outputs = []
    for call in function_calls:
        handler = function_handlers.get(call.name)
        if handler is None:
            raise RuntimeError(f'No handler registered for function "{call.name}".')
        result = handler(**json.loads(call.arguments))
        function_call_outputs.append(
            {
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": json.dumps(result),
            }
        )

    response = client.responses.create(
        model="subq-preview",
        previous_response_id=response.id,
        input=function_call_outputs,
        # Resend tools so the model can request another function call.
        tools=tools,
    )

if any(item.type == "function_call" for item in response.output):
    raise RuntimeError(f"Exceeded {max_function_rounds} function-calling rounds.")

print(get_last_assistant_text(response))
```

## Text preamble before tool calls

When tools ([web search](#web-search) or [function calling](#function-calling)) are enabled, the model may produce a short text preamble **before** it issues its tool calls — for example, "Let me look that up." This preamble is surfaced as its own assistant `message` output item, ordered **before** the tool-call item(s) it precedes. A single turn can therefore contain multiple `message` items: an opening preamble, and (for web search, which resolves within the same request) a final answer after the searches.

Implications for clients:

- Do not assume a tool-call turn has no `message`, and do not assume the assistant text is always `output[0]` or always last. Iterate `output` and dispatch on each item's `type`.
- Ordering follows the model: `output` may be `[message (preamble), web_search_call, message (final answer)]`, or `[message (preamble), function_call]`.
- When streaming, the preamble arrives as `response.output_text.delta` at its own `output_index` (before the tool items), exactly like any other assistant text. See [Streaming](#streaming).

## Request examples

Basic request with system instructions:

```bash title="cURL"
curl --request POST \
  --url https://api.subq.ai/v1/responses \
  --header "Authorization: Bearer $SUBQ_API_KEY" \
  --header 'Content-Type: application/json' \
  --data '
{
  "model": "subq-preview",
  "instructions": "You are a legal research assistant. Use plain language. Cite only facts in the conversation.",
  "input": "Summarize the major self-preferencing antitrust cases since 2010 and list open questions for counsel."
}
'
```

```ts title="TypeScript"
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.SUBQ_API_KEY,
  baseURL: "https://api.subq.ai/v1",
});

const response = await client.responses.create({
  model: "subq-preview",
  instructions: "You are a legal research assistant. Use plain language. Cite only facts in the conversation.",
  input: "Summarize the major self-preferencing antitrust cases since 2010 and list open questions for counsel."
});

console.log(response.output[0].content[0].text);
```

```py title="Python"
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
)

response = client.responses.create(
    model="subq-preview",
    instructions="You are a legal research assistant. Use plain language. Cite only facts in the conversation.",
    input="Summarize the major self-preferencing antitrust cases since 2010 and list open questions for counsel.",
)

print(response.output[0].content[0].text)
```

## Response

A non-streaming request returns a Response object:

```json {6,21,28-33}
{
  "id": "resp_01939abc1234567890abcdef",
  "object": "response",
  "created_at": 1768000000,
  "completed_at": 1768000001,
  "status": "completed",
  "model": "subq-preview",
  "output": [
    {
      "id": "msg_019f42995d097843a2bbdada3a046f14",
      "type": "message",
      "role": "assistant",
      "status": "completed",
      "phase": "final_answer",
      "content": [
        {
          "type": "output_text",
          "text": "Self-preferencing means a platform favors its own products over competitors. Major cases since 2010 include the EU Google Shopping decision and related follow-on actions. Open questions for counsel often include how to define the relevant market and how to measure harm to rivals.",
          "annotations": [],
          "logprobs": []
        }
      ]
    }
  ],
  "usage": {
    "input_tokens": 100,
    "input_tokens_details": { "cached_tokens": 0 },
    "output_tokens": 68,
    "output_tokens_details": { "reasoning_tokens": 0 },
    "total_tokens": 168
  },
  "instructions": "You are a legal research assistant. Use plain language. Cite only facts in the conversation.",
  "previous_response_id": null,
  "tools": [],
  "text": { "format": { "type": "text" } },
  "error": null,
  "incomplete_details": null
}
```

### Extracting the assistant text

Without tools, the assistant message is `output[0]`:

```
response.output[0].content[0].text
```

When tools run, `output` may contain `web_search_call` / `function_call` items, and the model may emit a text preamble `message` before them (see [Text preamble before tool calls](#text-preamble-before-tool-calls)). Don't assume the assistant text is at index `0` or that there is exactly one `message` — select message items by `type`, and take the **last** one as the final answer:

```js
const messages = response.output.filter((item) => item.type === "message");
const text = messages.at(-1)?.content[0]?.text ?? "";
```

Save `response.id` for the next turn's `previous_response_id`.

### Key response fields

| Field                                           | Description                                                                                                                                                                                                                               |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`                                            | Stable response ID for `previous_response_id`.                                                                                                                                                                                            |
| `status`                                        | `in_progress`, `completed`, `failed`, or `cancelled`.                                                                                                                                                                                     |
| `output`                                        | Ordered items for this turn: `message`, `web_search_call`, and/or `function_call`, in production order (a text preamble `message` may precede tool-call items — see [Text preamble before tool calls](#text-preamble-before-tool-calls)). |
| `usage`                                         | Token counts for this turn only (not the full conversation history).                                                                                                                                                                      |
| `instructions` / `tools` / `text` / `reasoning` | Echo of request fields.                                                                                                                                                                                                                   |
| `metadata`                                      | Echo of the request's `metadata`, or `{}` if none was sent. See [Metadata](#metadata).                                                                                                                                                    |
| `conversation`                                  | Present on every turn: `{ "id": "conv_..." }` identifying the conversation this response belongs to. See the [Conversations API](/endpoints/conversations-api/).                                                                          |

Other request fields such as `temperature`, `store`, and `tool_choice` may also be echoed.

### Output items

| `type`            | Meaning                                                                                                                                                     |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `message`         | Assistant text. Read `content[].text` where `type` is `output_text`. A turn may include more than one — a preamble before tool calls, and the final answer. |
| `web_search_call` | A completed search. See `action.queries` / `action.query`.                                                                                                  |
| `function_call`   | A function call generated by the model. See `call_id`, `name`, `arguments`, and [Function calling](#function-calling).                                      |

### Usage fields

| Field                                | Description                                                              |
| ------------------------------------ | ------------------------------------------------------------------------ |
| `input_tokens`                       | Tokens from the current turn's input (including web-search loop rounds). |
| `input_tokens_details.cached_tokens` | Prompt tokens served from cache.                                         |
| `output_tokens`                      | Tokens generated in the response.                                        |
| `total_tokens`                       | Sum of input and output tokens.                                          |

## Multi-turn conversations

Pass the `id` from a previous response as `previous_response_id` to continue. The server rebuilds history automatically — send only the new `input` and the prior response ID.

```
Turn 1:  POST /v1/responses
         { "model": "subq-preview", "input": "Who won the 2024 Nobel Prize in Physics?" }
         ← { "id": "resp_019f42fa...", "output": [{ "content": [{ "text": "John J. Hopfield and Geoffrey E. Hinton — for foundational work on machine learning with artificial neural networks." }] }] }

Turn 2:  POST /v1/responses
         { "model": "subq-preview", "input": "How does this connect to modern deep learning?", "previous_response_id": "resp_019f42fa..." }
         ← { "id": "resp_019f430a...", "previous_response_id": "resp_019f42fa...", "output": [{ "content": [{ "text": "Hopfield networks inspired associative memory and energy-based models; Hinton's backpropagation and deep networks underpin today's CNNs, transformers, and LLMs." }] }] }

Turn 3:  POST /v1/responses
         { "model": "subq-preview", "input": "Are there any other physics-inspired ML ideas not from these laureates?", "previous_response_id": "resp_019f430a..." }
         ← { "id": "resp_019f4319...", "previous_response_id": "resp_019f430a...", "output": [{ "content": [{ "text": "Yes — Boltzmann machines, diffusion models, renormalization-group analyses of deep networks, and thermodynamics-inspired views of SGD, among others." }] }] }
```

Chain turns by passing the latest `id` as `previous_response_id`. Resend `instructions` (and `tools`, if needed) on each turn — they are not inherited.

### Continuing by conversation id

Every response includes a `conversation.id`. Pass it as `conversation` on a later turn to continue instead of using a specific response id:

```json
{
  "model": "subq-preview",
  "input": "What is my name?",
  "conversation": "conv_abc123"
}
```

Use one or the other, not both — sending both `conversation` and `previous_response_id` returns `400`.

**Key behaviors:**

- History is **branch-safe**: branching from an older `previous_response_id` creates a new conversation branch rather than corrupting the existing chain.
- `usage.input_tokens` reflects the full conversation history resent each turn, not just the new input.
- Prior web searches are replayed into context so the model retains what it found.
- If `previous_response_id` or `conversation` does not exist, the server returns `404` immediately, before inference.

To manage the conversation itself — seed it with history up front, add or read back items, retag its metadata, or delete it — see the [Conversations API](/endpoints/conversations-api/).

## Streaming

When `stream: true`, the response is SSE (`Content-Type: text/event-stream`). Lifecycle events are always present; tools add output-item events.

**Lifecycle:** `response.created` → `response.output_text.delta`… → `response.completed`

**Output items (when tools run):** `response.output_item.added` → item progress events → `response.output_item.done`

```
event: response.created
data: { "type": "response.created", "sequence_number": 0, "response": { ... } }

event: response.output_text.delta
data: { "type": "response.output_text.delta", "sequence_number": 1, "delta": "Self" }

event: response.completed
data: { "type": "response.completed", "sequence_number": 2, "response": { ... } }
```

| Event type                                                         | When                                                                                                                                                              |
| ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `response.created`                                                 | First. Skeleton response (`status: "in_progress"`). Use `response.id` for the next turn.                                                                          |
| `response.output_text.delta`                                       | Text chunk of assistant text — the final answer, or a [preamble](#text-preamble-before-tool-calls) before tool calls. Concatenate `delta` values per output item. |
| `response.completed`                                               | Last. Full `output` and `usage`.                                                                                                                                  |
| `response.output_item.added` / `done`                              | A structured output item (`web_search_call` or `function_call`) is created / finalized.                                                                           |
| `response.web_search_call.in_progress` / `searching` / `completed` | Status pings while a search runs. Queries appear on `output_item.done`.                                                                                           |
| `response.function_call_arguments.delta` / `done`                  | Streamed `arguments` for a `function_call`. Concatenate `delta` values, then parse `done`'s `arguments` as JSON.                                                  |

Items are ordered by `output_index`, incrementing per item in the order the model produced them. A [text preamble](#text-preamble-before-tool-calls) is a `message` item and takes the index **before** the tool-call item(s) it precedes; the final answer message takes the index after the last item. The model's internal tool-call planning is never streamed — only the resulting items and assistant text reach the client.

Treat unknown event types as ignorable. The stream ends after `response.completed` — not `data: [DONE]`. A `: keepalive` comment is emitted every 15s while the model is slow. If the stream closes without `response.completed`, treat it as an error and retry.

```bash title="cURL"
curl --request POST \
  --url https://api.subq.ai/v1/responses \
  --header "Authorization: Bearer $SUBQ_API_KEY" \
  --header 'Content-Type: application/json' \
  --data '
{
  "model": "subq-preview",
  "input": "Summarize the major self-preferencing antitrust cases since 2010.",
  "stream": true
}
'
```

```ts title="TypeScript"
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.SUBQ_API_KEY,
  baseURL: "https://api.subq.ai/v1",
});

const stream = await client.responses.create({
  model: "subq-preview",
  input: "Summarize the major self-preferencing antitrust cases since 2010.",
  stream: true
});

let fullText = "";
let responseId = null;

for await (const event of stream) {
  if (event.type === "response.created") {
    responseId = event.response.id;
    continue;
  }

  if (event.type === "response.output_text.delta") {
    fullText += event.delta;
    process.stdout.write(event.delta);
    continue;
  }

  if (event.type === "response.completed") {
    // event.response has full output and usage
    continue;
  }
}

console.log(); // newline after streamed tokens
console.log(fullText);
console.log(responseId); // use as previous_response_id on the next turn
```

```py title="Python"
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
)

stream = client.responses.create(
    model="subq-preview",
    input="Summarize the major self-preferencing antitrust cases since 2010.",
    stream=True,
)

full_text = ""
response_id = None

for event in stream:
    if event.type == "response.created":
        response_id = event.response.id
        continue

    if event.type == "response.output_text.delta":
        full_text += event.delta
        print(event.delta, end="", flush=True)
        continue

    if event.type == "response.completed":
        # event.response has full output and usage
        continue

print()
print(full_text)
print(response_id)  # use as previous_response_id on the next turn
```

## Structured outputs

Set `text.format` to constrain the model's output — see [Structured outputs](/using-the-api/structured-outputs/) for schema design guidance. Three modes are supported:

| Mode             | Shape                                                                         | Guarantee                                                |
| ---------------- | ----------------------------------------------------------------------------- | -------------------------------------------------------- |
| `text` (default) | `{ "type": "text" }`                                                          | Unconstrained text.                                      |
| `json_object`    | `{ "type": "json_object" }`                                                   | Output is valid JSON, but not constrained to any schema. |
| `json_schema`    | `{ "type": "json_schema", "name": "...", "strict": true, "schema": { ... } }` | Output conforms to the supplied JSON Schema.             |

Note the **flattened** shape: `name`, `strict`, and `schema` sit directly on `text.format` — unlike Chat Completions, where they nest under `response_format.json_schema`.

```json
{
  "model": "subq-preview",
  "input": "RFI-042 from Structural: Confirm rebar grade for Level 3 slab. Spec section 03 20 00 says Grade 60. Reply needed by 2026-07-18 before pour.",
  "text": {
    "format": {
      "type": "json_schema",
      "name": "rfi_extract",
      "strict": true,
      "schema": {
        "type": "object",
        "properties": {
          "rfi_id": { "type": "string" },
          "from_trade": { "type": "string" },
          "question": { "type": "string" },
          "spec_section": { "type": "string" },
          "due_date": { "type": "string" }
        },
        "required": ["rfi_id", "from_trade", "question", "spec_section", "due_date"],
        "additionalProperties": false
      }
    }
  }
}
```

Example output at `output[0].content[0].text` (parse the string to get the object):

```json
{
  "rfi_id": "RFI-042",
  "from_trade": "Structural",
  "question": "Confirm rebar grade for Level 3 slab. Spec section 03 20 00 says Grade 60.",
  "spec_section": "03 20 00",
  "due_date": "2026-07-18"
}
```

The structured JSON arrives as ordinary assistant text at `output[0].content[0].text` — parse that string to get the object. `json_schema` guarantees a valid shape; for reliable field values, put the facts in `input` and ask the model to extract them (as above).

Unlike OpenAI, `json_object` mode does not require the word "JSON" in your prompt — output is grammar-constrained by the model server.

For a yes/no, category, or rating judgment with probabilities, use the [Decisions API](/endpoints/decisions-api/).

## Metadata

Attach up to 16 key-value string pairs to a request for your own tracking — run IDs, experiment names, customer tags. SubQ does not interpret or act on these values.

- Keys can be at most 64 characters; values at most 512 characters.
- Values must be strings. Numbers and booleans are coerced to strings; objects, arrays, and other non-string values are rejected with a `400` `validation_error`.
- Omit `metadata`, or pass `null` or `{}`, for no metadata — all three are treated the same.

```json
{
  "model": "subq-preview",
  "input": "Summarize the major self-preferencing antitrust cases since 2010.",
  "metadata": { "run_id": "eval-2026-08-31-014", "experiment": "reasoning-ablation" }
}
```

The response echoes `metadata` back verbatim — on the non-streaming response object, and on both the `response.created` and `response.completed` streaming events:

```json
{
  "id": "resp_01939abc1234567890abcdef",
  "metadata": { "run_id": "eval-2026-08-31-014", "experiment": "reasoning-ablation" }
}
```

`metadata` is never forwarded to the underlying model — it is for your own request tracking only.

## Storage

By default every turn is saved so later turns can continue from it. Saved turns stay until you [delete the conversation](/endpoints/conversations-api/#delete-a-conversation); see [Data retention](/using-the-api/data-retention/). Set `store: false` to run a turn without saving it. The turn can still read earlier history:

```json
{
  "model": "subq-preview",
  "input": "Which of those medications interact with warfarin?",
  "previous_response_id": "resp_019f42fa...",
  "store": false
}
```

An unsaved turn isn't part of the history, and can't be continued from later.

## Errors

```json
{
  "error": {
    "message": "Response 'resp_xxx' not found.",
    "type": "server_error",
    "code": "response_not_found"
  }
}
```

Use `code` for programmatic handling — `message` text may change.

Shared codes with Chat Completions include `invalid_api_key`, `insufficient_credits`, `validation_error`, `rate_limit_exceeded`, and `model_not_allowed` (`403`, the model is not enabled for your organization; see [SubQ Preview](/using-the-api/models/#subq-preview)). Responses-specific:

| HTTP | `code`                   | Meaning                                                                            |
| ---- | ------------------------ | ---------------------------------------------------------------------------------- |
| 400  | `validation_error`       | `input_file` is missing `file_id`, or the part used unsupported inline `file_data` |
| 404  | `response_not_found`     | `previous_response_id` does not exist in the store                                 |
| 404  | `conversation_not_found` | `conversation` does not exist or belongs to another organization                   |
| 404  | `file_not_found`         | `file_id` does not exist or is owned by another organization                       |
| 503  | `authorization_failed`   | Key lookup temporarily unavailable; retry                                          |

See the [Conversations API](/endpoints/conversations-api/#errors) for conversation-specific error codes.

See [Authentication](/using-the-api/authentication/) for auth and credit errors.

## Next steps

- [Authentication](/using-the-api/authentication/) — API keys and request headers.
- [Models](/using-the-api/models/) — supported model IDs and context windows.
- [Sending files](/using-the-api/file-inputs/) — `input_file` vs Chat Completions `file` parts.
- [Files API](/endpoints/files-api/) — upload and manage files referenced by `file_id`.
- [Conversations API](/endpoints/conversations-api/) — manage conversation history as a stored resource.
- [Structured outputs](/using-the-api/structured-outputs/) — schema design for `text.format`.
- [Function calling](/using-the-api/function-calling/) — tool calling concepts and Chat Completions' nested function-tool shape, for comparison with [Responses function calling](#function-calling).
- [Chat Completions API](/endpoints/chat-completions-api/) — stateless, drop-in OpenAI replacement.
