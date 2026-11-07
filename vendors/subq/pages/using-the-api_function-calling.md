---
title: Function calling
description: Connect SubQ models to your application with OpenAI-compatible tools, on Chat Completions or the Responses API.
---

> Status: Early access

Function calling (also known as tool calling) lets SubQ models interface with
external systems and data outside their training data. Pass function tools
defined by a JSON schema in the `tools` parameter; the model may return a
**tool call**, and your application executes the function and sends the
**tool call output** back so the model can finish the reply. The shape
differs by endpoint: Responses uses a flattened tool object
(`type`/`name`/`parameters` directly on it), while Chat Completions nests
those fields under a `function` object.

On Chat Completions, SubQ currently returns `tool_calls` reliably when
`stream` is `true`. Accumulate streamed deltas into a full assistant message
before executing tools — non-streaming responses may set `finish_reason` to
`"tool_calls"` without including the `tool_calls` payload.

## How it works

**Tools** — functionality you give the model. A function tool is a JSON Schema
definition the model can choose to call, for example `get_stock_quote`, account
lookup, or issuing a refund.

**Tool calls** — requests from the model to use a tool. If the prompt needs
live data, the model returns one or more calls, each with a function `name`
and JSON-encoded arguments.

**Tool call outputs** — results your application sends back so the model can
finish the reply.

### The tool calling flow

1. Make a request to the model with tools it could call
2. Receive a tool call from the model
3. Execute code on the application side with input from the tool call
4. Make a second request to the model with the tool output
5. Receive a final response from the model (or more tool calls)

## Field reference

|                     | Responses API                                                                     | Chat Completions                                                                       |
| ------------------- | --------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| Tool shape          | `type`, `name`, `description`, `parameters`, `strict` directly on the tool object | `type: "function"` plus a nested `function: { name, description, parameters, strict }` |
| Tool call           | `function_call` output item — `call_id`, `name`, `arguments`                      | `tool_calls[]` on the assistant message — `id`, `function: { name, arguments }`        |
| Sending the result  | `function_call_output` input item — `call_id`, `output`                           | A message with `role: "tool"`, `tool_call_id`, `content`                               |
| Streaming           | `response.function_call_arguments.delta`/`.done` events                           | `delta.tool_calls[]`, keyed by `index`                                                 |
| Continuing the loop | `previous_response_id` (or `conversation`)                                        | Resend the full `messages[]`, including the assistant and tool messages                |

Both accept the same JSON Schema shape in `parameters`, and the same [strict
mode](#strict-mode) requirements.

## Example

End-to-end flow for a `get_stock_quote` function: the first request declares
the tool, the model returns a tool call, your code runs the function and
sends the result back for a final answer.

```bash title="cURL"
curl --request POST \
  --url https://api.subq.ai/v1/responses \
  --header "Authorization: Bearer $SUBQ_API_KEY" \
  --header 'Content-Type: application/json' \
  --data @- <<'EOF'
{
  "model": "subq-preview",
  "input": "What's NVDA trading at right now?",
  "tools": [
    {
      "type": "function",
      "name": "get_stock_quote",
      "description": "Retrieves the latest quote for a stock ticker.",
      "parameters": {
        "type": "object",
        "properties": {
          "symbol": {
            "type": "string",
            "description": "Ticker symbol, e.g. NVDA or MSFT"
          },
          "currency": {
            "type": [
              "string",
              "null"
            ],
            "enum": [
              "USD",
              "EUR"
            ],
            "description": "Quote currency. Defaults to USD when null."
          },
          "include_extended_hours": {
            "type": "boolean",
            "description": "When true, include pre-market and after-hours price if available."
          }
        },
        "required": [
          "symbol",
          "currency",
          "include_extended_hours"
        ],
        "additionalProperties": false
      },
      "strict": true
    }
  ]
}
EOF
```

```ts title="TypeScript"
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.SUBQ_API_KEY,
  baseURL: "https://api.subq.ai/v1",
});

const response = await client.responses.create({
  model: "subq-preview",
  input: "What's NVDA trading at right now?",
  tools: [
    {
      type: "function",
      name: "get_stock_quote",
      description: "Retrieves the latest quote for a stock ticker.",
      parameters: {
        type: "object",
        properties: {
          symbol: {
            type: "string",
            description: "Ticker symbol, e.g. NVDA or MSFT"
          },
          currency: {
            type: [
              "string",
              "null"
            ],
            enum: [
              "USD",
              "EUR"
            ],
            description: "Quote currency. Defaults to USD when null."
          },
          include_extended_hours: {
            type: "boolean",
            description: "When true, include pre-market and after-hours price if available."
          }
        },
        required: [
          "symbol",
          "currency",
          "include_extended_hours"
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
    input="What's NVDA trading at right now?",
    tools=[
        {
            "type": "function",
            "name": "get_stock_quote",
            "description": "Retrieves the latest quote for a stock ticker.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Ticker symbol, e.g. NVDA or MSFT",
                    },
                    "currency": {
                        "type": [
                            "string",
                            "null",
                        ],
                        "enum": [
                            "USD",
                            "EUR",
                        ],
                        "description": "Quote currency. Defaults to USD when null.",
                    },
                    "include_extended_hours": {
                        "type": "boolean",
                        "description": "When true, include pre-market and after-hours price if available.",
                    },
                },
                "required": [
                    "symbol",
                    "currency",
                    "include_extended_hours",
                ],
                "additionalProperties": False,
            },
            "strict": True,
        },
    ],
)

print(response.output[0].content[0].text)
```

Accumulate any text preamble, execute every `function_call` in the turn, then
continue with one `function_call_output` per `call_id`:

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

Set `stream` to `true` and include your function definitions in `tools`.

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
      "content": "What's NVDA trading at right now?"
    }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_stock_quote",
        "description": "Retrieves the latest quote for a stock ticker.",
        "parameters": {
          "type": "object",
          "properties": {
            "symbol": {
              "type": "string",
              "description": "Ticker symbol, e.g. NVDA or MSFT"
            },
            "currency": {
              "type": [
                "string",
                "null"
              ],
              "enum": [
                "USD",
                "EUR"
              ],
              "description": "Quote currency. Defaults to USD when null."
            },
            "include_extended_hours": {
              "type": "boolean",
              "description": "When true, include pre-market and after-hours price if available."
            }
          },
          "required": [
            "symbol",
            "currency",
            "include_extended_hours"
          ],
          "additionalProperties": false
        },
        "strict": true
      }
    }
  ],
  "stream": true
}
EOF
```

```ts title="TypeScript"
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.SUBQ_API_KEY,
  baseURL: "https://api.subq.ai/v1",
});

const stream = await client.chat.completions.create({
  model: "subq-preview",
  messages: [
    {
      role: "user",
      content: "What's NVDA trading at right now?"
    }
  ],
  tools: [
    {
      type: "function",
      function: {
        name: "get_stock_quote",
        description: "Retrieves the latest quote for a stock ticker.",
        parameters: {
          type: "object",
          properties: {
            symbol: {
              type: "string",
              description: "Ticker symbol, e.g. NVDA or MSFT"
            },
            currency: {
              type: [
                "string",
                "null"
              ],
              enum: [
                "USD",
                "EUR"
              ],
              description: "Quote currency. Defaults to USD when null."
            },
            include_extended_hours: {
              type: "boolean",
              description: "When true, include pre-market and after-hours price if available."
            }
          },
          required: [
            "symbol",
            "currency",
            "include_extended_hours"
          ],
          additionalProperties: false
        },
        strict: true
      }
    }
  ],
  stream: true
});

let fullText = "";

for await (const chunk of stream) {
  const delta = chunk.choices[0]?.delta?.content ?? "";
  fullText += delta;
  process.stdout.write(delta);
}

console.log();
console.log(fullText);
```

```py title="Python"
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
)

stream = client.chat.completions.create(
    model="subq-preview",
    messages=[
        {
            "role": "user",
            "content": "What's NVDA trading at right now?",
        },
    ],
    tools=[
        {
            "type": "function",
            "function": {
                "name": "get_stock_quote",
                "description": "Retrieves the latest quote for a stock ticker.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Ticker symbol, e.g. NVDA or MSFT",
                        },
                        "currency": {
                            "type": [
                                "string",
                                "null",
                            ],
                            "enum": [
                                "USD",
                                "EUR",
                            ],
                            "description": "Quote currency. Defaults to USD when null.",
                        },
                        "include_extended_hours": {
                            "type": "boolean",
                            "description": "When true, include pre-market and after-hours price if available.",
                        },
                    },
                    "required": [
                        "symbol",
                        "currency",
                        "include_extended_hours",
                    ],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        },
    ],
    stream=True,
)

full_text = ""

for chunk in stream:
    delta = chunk.choices[0].delta.content or ""
    full_text += delta
    print(delta, end="", flush=True)

print()
print(full_text)
```

Accumulate streamed `delta.tool_calls` into one assistant message, execute
each call, append `role: "tool"` results, then call the model again:

```ts title="TypeScript"
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.SUBQ_API_KEY,
  baseURL: "https://api.subq.ai/v1",
  maxRetries: 0,
});

// 1. Define callable tools for the model
const tools = [
  {
    type: "function",
    function: {
      name: "get_stock_quote",
      description: "Retrieves the latest quote for a stock ticker.",
      parameters: {
        type: "object",
        properties: {
          symbol: {
            type: "string",
            description: "Ticker symbol, e.g. NVDA or MSFT",
          },
          currency: {
            type: ["string", "null"],
            enum: ["USD", "EUR"],
            description: "Quote currency. Defaults to USD when null.",
          },
          include_extended_hours: {
            type: "boolean",
            description:
              "When true, include pre-market and after-hours price if available.",
          },
        },
        required: ["symbol", "currency", "include_extended_hours"],
        additionalProperties: false,
      },
      strict: true,
    },
  },
];

function getStockQuote({ symbol, currency, include_extended_hours }) {
  const quoteCurrency = currency ?? "USD";
  return JSON.stringify({
    symbol: symbol.toUpperCase(),
    price: 210.96,
    currency: quoteCurrency,
    change: 8.18,
    change_percent: 4.03,
    open: 202.0,
    high: 211.0,
    low: 201.92,
    previous_close: 202.78,
    market_cap: 5.11e12,
    pe_ratio: 32.31,
    market_open: false,
    extended_hours: include_extended_hours
      ? {
          price: 210.38,
          change: -0.58,
          change_percent: -0.27,
          session: "after_hours",
        }
      : null,
    as_of: "2026-07-10T21:22:00Z",
  });
}

/** Accumulate streamed chat.completion chunks into one assistant message. */
async function createCompletion(messages) {
  const stream = await client.chat.completions.create({
    model: "subq-preview",
    messages,
    tools,
    stream: true,
  });

  const message = {
    role: "assistant",
    content: null,
    tool_calls: [],
  };

  for await (const chunk of stream) {
    const delta = chunk.choices[0]?.delta;
    if (!delta) continue;

    if (typeof delta.content === "string") {
      message.content = (message.content ?? "") + delta.content;
    }

    for (const toolCall of delta.tool_calls ?? []) {
      const index = toolCall.index ?? 0;
      if (!message.tool_calls[index]) {
        message.tool_calls[index] = {
          id: toolCall.id,
          type: toolCall.type ?? "function",
          function: {
            name: toolCall.function?.name ?? "",
            arguments: toolCall.function?.arguments ?? "",
          },
        };
        continue;
      }

      if (toolCall.id) message.tool_calls[index].id = toolCall.id;
      if (toolCall.function?.name) {
        message.tool_calls[index].function.name += toolCall.function.name;
      }
      if (toolCall.function?.arguments) {
        message.tool_calls[index].function.arguments +=
          toolCall.function.arguments;
      }
    }
  }

  if (message.tool_calls.length === 0) {
    delete message.tool_calls;
  }

  return message;
}

const messages = [
  { role: "user", content: "What's NVDA trading at right now?" },
];

// 2. Prompt the model with tools available
let message = await createCompletion(messages);
messages.push(message);

if (!message.tool_calls?.length) {
  console.log(message.content);
  process.exit(0);
}

// 3. Execute each tool call on the application side
for (const toolCall of message.tool_calls) {
  if (toolCall.function.name !== "get_stock_quote") continue;

  const args = JSON.parse(toolCall.function.arguments);
  const result = getStockQuote(args);

  // 4. Provide tool call outputs back to the model
  messages.push({
    role: "tool",
    tool_call_id: toolCall.id,
    content: result,
  });
}

// 5. Receive a final response (or more tool calls)
message = await createCompletion(messages);
console.log(message.content);
```

```py title="Python"
import json
import os

from openai import OpenAI

client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
    max_retries=0,
)

# 1. Define callable tools for the model
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_quote",
            "description": "Retrieves the latest quote for a stock ticker.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Ticker symbol, e.g. NVDA or MSFT",
                    },
                    "currency": {
                        "type": ["string", "null"],
                        "enum": ["USD", "EUR"],
                        "description": "Quote currency. Defaults to USD when null.",
                    },
                    "include_extended_hours": {
                        "type": "boolean",
                        "description": (
                            "When true, include pre-market and after-hours "
                            "price if available."
                        ),
                    },
                },
                "required": ["symbol", "currency", "include_extended_hours"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }
]


def get_stock_quote(symbol, currency=None, include_extended_hours=False):
    quote_currency = currency or "USD"
    return json.dumps(
        {
            "symbol": symbol.upper(),
            "price": 210.96,
            "currency": quote_currency,
            "change": 8.18,
            "change_percent": 4.03,
            "open": 202.0,
            "high": 211.0,
            "low": 201.92,
            "previous_close": 202.78,
            "market_cap": 5.11e12,
            "pe_ratio": 32.31,
            "market_open": False,
            "extended_hours": (
                {
                    "price": 210.38,
                    "change": -0.58,
                    "change_percent": -0.27,
                    "session": "after_hours",
                }
                if include_extended_hours
                else None
            ),
            "as_of": "2026-07-10T21:22:00Z",
        }
    )


def create_completion(messages):
    """Accumulate streamed chat.completion chunks into one assistant message."""
    stream = client.chat.completions.create(
        model="subq-preview",
        messages=messages,
        tools=tools,
        stream=True,
    )

    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [],
    }

    for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta is None:
            continue

        if isinstance(delta.content, str):
            message["content"] = (message["content"] or "") + delta.content

        for tool_call in delta.tool_calls or []:
            index = tool_call.index or 0
            if index >= len(message["tool_calls"]):
                message["tool_calls"].append(
                    {
                        "id": tool_call.id,
                        "type": tool_call.type or "function",
                        "function": {
                            "name": (tool_call.function.name or ""),
                            "arguments": (tool_call.function.arguments or ""),
                        },
                    }
                )
                continue

            existing = message["tool_calls"][index]
            if tool_call.id:
                existing["id"] = tool_call.id
            if tool_call.function.name:
                existing["function"]["name"] += tool_call.function.name
            if tool_call.function.arguments:
                existing["function"]["arguments"] += tool_call.function.arguments

    if not message["tool_calls"]:
        del message["tool_calls"]

    return message


messages = [
    {"role": "user", "content": "What's NVDA trading at right now?"},
]

# 2. Prompt the model with tools available
message = create_completion(messages)
messages.append(message)

if not message.get("tool_calls"):
    print(message.get("content"))
    raise SystemExit(0)

# 3. Execute each tool call on the application side
for tool_call in message["tool_calls"]:
    if tool_call["function"]["name"] != "get_stock_quote":
        continue

    args = json.loads(tool_call["function"]["arguments"])
    result = get_stock_quote(**args)

    # 4. Provide tool call outputs back to the model
    messages.append(
        {
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": result,
        }
    )

# 5. Receive a final response (or more tool calls)
message = create_completion(messages)
print(message.get("content"))
```

**Example assistant tool call** (after accumulating the stream):

```json
{
  "role": "assistant",
  "content": null,
  "tool_calls": [
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "get_stock_quote",
        "arguments": "{\"symbol\":\"NVDA\",\"currency\":\"USD\",\"include_extended_hours\":false}"
      }
    }
  ]
}
```

**Example tool message** you send back:

```json
{
  "role": "tool",
  "tool_call_id": "call_abc123",
  "content": "{\"symbol\":\"NVDA\",\"price\":210.96,\"currency\":\"USD\",\"change\":8.18,\"change_percent\":4.03,\"open\":202.0,\"high\":211.0,\"low\":201.92,\"previous_close\":202.78,\"market_cap\":5110000000000,\"pe_ratio\":32.31,\"market_open\":false,\"extended_hours\":null,\"as_of\":\"2026-07-10T21:22:00Z\"}"
}
```

A response can contain more calls after receiving outputs, so keep looping
until the model returns a final message — cap the number of rounds to avoid
runaway loops. Execute every call in a turn concurrently (the model may call
in parallel).

### Dispatching multiple tool calls

The model may return zero, one, or many calls in a single turn. Dispatch by
name and execute them concurrently; on Responses, resend `tools` on each
request where the model should be allowed to call again, and match outputs
back by `call_id` — the same rules as the single-tool loop above, just with
more than one call per turn. On Chat Completions:

```ts title="TypeScript"
function getAccountPositions({ account_id, symbol }) {
  const positions = [
    {
      symbol: "NVDA",
      quantity: 120,
      average_cost: 142.5,
      market_value: 25315.2,
    },
    {
      symbol: "MSFT",
      quantity: 40,
      average_cost: 380.1,
      market_value: 15404.0,
    },
  ];
  const filtered = symbol
    ? positions.filter((p) => p.symbol === symbol.toUpperCase())
    : positions;
  return JSON.stringify({ account_id, positions: filtered });
}

const handlers = {
  get_stock_quote: getStockQuote,
  get_account_positions: getAccountPositions,
};

// After createCompletion() — same streaming accumulator as the single-tool example
for (const toolCall of message.tool_calls ?? []) {
  const handler = handlers[toolCall.function.name];
  if (!handler) {
    throw new Error(`Unknown tool: ${toolCall.function.name}`);
  }
  const args = JSON.parse(toolCall.function.arguments);
  messages.push({
    role: "tool",
    tool_call_id: toolCall.id,
    content: handler(args),
  });
}
```

```py title="Python"
def get_account_positions(account_id, symbol=None):
    positions = [
        {
            "symbol": "NVDA",
            "quantity": 120,
            "average_cost": 142.5,
            "market_value": 25315.2,
        },
        {
            "symbol": "MSFT",
            "quantity": 40,
            "average_cost": 380.1,
            "market_value": 15404.0,
        },
    ]
    if symbol:
        positions = [p for p in positions if p["symbol"] == symbol.upper()]
    return json.dumps({"account_id": account_id, "positions": positions})


handlers = {
    "get_stock_quote": get_stock_quote,
    "get_account_positions": get_account_positions,
}

# After create_completion() — same streaming accumulator as the single-tool example
for tool_call in message.get("tool_calls") or []:
    handler = handlers.get(tool_call["function"]["name"])
    if handler is None:
        raise RuntimeError(f"Unknown tool: {tool_call['function']['name']}")
    args = json.loads(tool_call["function"]["arguments"])
    messages.append(
        {
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": handler(**args),
        }
    )
```

See [Responses function calling](/endpoints/responses-api/#function-calling)
for that endpoint's own parallel-call example.

### Strict mode

Set `strict` to `true` so function arguments adhere to the schema. Recommended
for production. Strict schemas require:

1. `additionalProperties` set to `false` on every object in `parameters`
2. Every key in `properties` listed in `required`

Mark a field optional by allowing `null` in its type (for example
`"type": ["string", "null"]`) while still listing it in `required`.

## Handling function calls

Assume zero, one, or many tool calls in a turn — see
[Dispatching multiple tool calls](#example) above.

1. Add the model's tool call(s) to your ongoing context (the assistant
   message on Chat Completions, or nothing extra to add on Responses — just
   continue via `previous_response_id`/`conversation`)
2. For each call, parse the arguments, run your code, and send back a result
   keyed by `call_id` (Responses) or `tool_call_id` (Chat Completions)
3. Call the model again with the result — the full `messages[]` on Chat
   Completions, or just the `function_call_output` items on Responses

The result is typically a string — JSON, plain text, or a short
success/failure token for side-effect-only functions (for example `"success"`).

## Tool choice

By default the model decides when to call tools. On Chat Completions, control
that with `tool_choice`:

| Value                                                       | Behavior                                       |
| ----------------------------------------------------------- | ---------------------------------------------- |
| `"auto"`                                                    | Default. Call zero, one, or multiple functions |
| `"required"`                                                | Call one or more functions                     |
| `"none"`                                                    | Do not call tools (same as omitting `tools`)   |
| `{"type":"function","function":{"name":"get_stock_quote"}}` | Force that specific function                   |

```json
{
  "tool_choice": {
    "type": "function",
    "function": { "name": "get_stock_quote" }
  }
}
```

Responses accepts the same `"auto"`/`"required"`/`"none"` string values
(defaulting to `"auto"` once `tools` is set) but doesn't support forcing one
specific function by name.

## Best practices

- **Write clear names and descriptions.** Say when to use the function, what
  each parameter means, and what the output represents. Use the system
  message or `instructions` for when *not* to call a tool.
- **Keep the tool list small.** Fewer tools usually improve accuracy; prefer a
  focused set over a large catalog in one turn.
- **Offload known values in code.** Do not ask the model to fill arguments you
  already know (for example an `order_id` from session state).
- **Enable strict mode** and validate parsed arguments in your application
  before executing side effects.

## Related

- [Responses API](/endpoints/responses-api/#function-calling) — request fields and streaming events for the flattened shape.
- [Chat Completions API](/endpoints/chat-completions-api/) — request fields and response shape for the nested shape.
- [Structured outputs](/using-the-api/structured-outputs/) — schema-constrained JSON replies.
- [Models](/using-the-api/models/) — which models support tool calls.
- [OpenAI Function calling](https://developers.openai.com/api/docs/guides/function-calling) — full OpenAI reference.
