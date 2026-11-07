---
title: Structured outputs
description: Return JSON that matches your schema, from the Responses API or Chat Completions.
---

> Status: Early access

Structured Outputs ensures the model's reply matches your JSON Schema — set
`text.format.type` (Responses) or `response_format.type` (Chat Completions) to
`"json_schema"` and define your schema (`name` and `schema`).

For a yes/no, category, or rating judgment with probabilities, use the
[Decisions API](/endpoints/decisions-api/) instead.

## Field reference

|                 | Responses API                     | Chat Completions                      |
| --------------- | --------------------------------- | ------------------------------------- |
| Enable          | `text.format.type: "json_schema"` | `response_format.type: "json_schema"` |
| Schema name     | `text.format.name`                | `response_format.json_schema.name`    |
| Strict mode     | `text.format.strict`              | `response_format.json_schema.strict`  |
| Schema          | `text.format.schema`              | `response_format.json_schema.schema`  |
| Output location | `output[0].content[0].text`       | `choices[0].message.content`          |

Note the Responses shape is **flattened** — `name`, `strict`, and `schema`
sit directly on `text.format` — while Chat Completions nests them under
`response_format.json_schema`. Both accept the same JSON Schema shape in
`schema`.

### Schema requirements

- Root type must be `object`.
- List every property in `required`.
- Set `additionalProperties: false` on each object.
- Supported types: `string`, `number`, `boolean`, `integer`, `enum`, `array`, nested `object`.

There is no native datetime type—use a `string` field with ISO 8601 in the name or
description (for example, `submit_by`, `detected_at`).

For the full constraint list, see OpenAI's
[supported schemas](https://developers.openai.com/api/docs/guides/structured-outputs#supported-schemas).

## Example

List Nobel Peace Prize winners from 2022 through 2024, classifying each as a
person or an organization.

```bash title="cURL"
curl --request POST \
  --url https://api.subq.ai/v1/responses \
  --header "Authorization: Bearer $SUBQ_API_KEY" \
  --header 'Content-Type: application/json' \
  --data '
{
  "model": "subq-preview",
  "instructions": "Return Nobel Peace Prize laureates for only the year range in the user message. One array entry per laureate (shared prizes produce multiple entries with the same year). Set kind to 👤 for a person and 🏛️ for an organization or institution. Use ISO 3166-1 alpha-2 country codes. Keep each motivation to one sentence.",
  "input": "List Nobel Peace Prize winners from 2022 through 2024.",
  "text": {
    "format": {
      "type": "json_schema",
      "name": "nobel_peace_laureates",
      "strict": true,
      "schema": {
        "type": "object",
        "properties": {
          "laureates": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "year": {
                  "type": "integer"
                },
                "name": {
                  "type": "string"
                },
                "kind": {
                  "type": "string",
                  "enum": [
                    "👤",
                    "🏛️"
                  ],
                  "description": "👤 for a person; 🏛️ for an organization or institution"
                },
                "country_code": {
                  "type": "string",
                  "description": "ISO 3166-1 alpha-2"
                },
                "motivation": {
                  "type": "string",
                  "description": "One-sentence citation summary"
                }
              },
              "required": [
                "year",
                "name",
                "kind",
                "country_code",
                "motivation"
              ],
              "additionalProperties": false
            }
          }
        },
        "required": [
          "laureates"
        ],
        "additionalProperties": false
      }
    }
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
  instructions: "Return Nobel Peace Prize laureates for only the year range in the user message. One array entry per laureate (shared prizes produce multiple entries with the same year). Set kind to 👤 for a person and 🏛️ for an organization or institution. Use ISO 3166-1 alpha-2 country codes. Keep each motivation to one sentence.",
  input: "List Nobel Peace Prize winners from 2022 through 2024.",
  text: {
    format: {
      type: "json_schema",
      name: "nobel_peace_laureates",
      strict: true,
      schema: {
        type: "object",
        properties: {
          laureates: {
            type: "array",
            items: {
              type: "object",
              properties: {
                year: {
                  type: "integer"
                },
                name: {
                  type: "string"
                },
                kind: {
                  type: "string",
                  enum: [
                    "👤",
                    "🏛️"
                  ],
                  description: "👤 for a person; 🏛️ for an organization or institution"
                },
                country_code: {
                  type: "string",
                  description: "ISO 3166-1 alpha-2"
                },
                motivation: {
                  type: "string",
                  description: "One-sentence citation summary"
                }
              },
              required: [
                "year",
                "name",
                "kind",
                "country_code",
                "motivation"
              ],
              additionalProperties: false
            }
          }
        },
        required: [
          "laureates"
        ],
        additionalProperties: false
      }
    }
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
    instructions="Return Nobel Peace Prize laureates for only the year range in the user message. One array entry per laureate (shared prizes produce multiple entries with the same year). Set kind to 👤 for a person and 🏛️ for an organization or institution. Use ISO 3166-1 alpha-2 country codes. Keep each motivation to one sentence.",
    input="List Nobel Peace Prize winners from 2022 through 2024.",
    text={
        "format": {
            "type": "json_schema",
            "name": "nobel_peace_laureates",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "laureates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "year": {
                                    "type": "integer",
                                },
                                "name": {
                                    "type": "string",
                                },
                                "kind": {
                                    "type": "string",
                                    "enum": [
                                        "👤",
                                        "🏛️",
                                    ],
                                    "description": "👤 for a person; 🏛️ for an organization or institution",
                                },
                                "country_code": {
                                    "type": "string",
                                    "description": "ISO 3166-1 alpha-2",
                                },
                                "motivation": {
                                    "type": "string",
                                    "description": "One-sentence citation summary",
                                },
                            },
                            "required": [
                                "year",
                                "name",
                                "kind",
                                "country_code",
                                "motivation",
                            ],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": [
                    "laureates",
                ],
                "additionalProperties": False,
            },
        },
    },
)

print(response.output[0].content[0].text)
```

The model returns schema-valid JSON as a string at `output[0].content[0].text`.

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
      "content": "Return Nobel Peace Prize laureates for only the year range in the user message. One array entry per laureate (shared prizes produce multiple entries with the same year). Set kind to 👤 for a person and 🏛️ for an organization or institution. Use ISO 3166-1 alpha-2 country codes. Keep each motivation to one sentence."
    },
    {
      "role": "user",
      "content": "List Nobel Peace Prize winners from 2022 through 2024."
    }
  ],
  "stream": false,
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "nobel_peace_laureates",
      "strict": true,
      "schema": {
        "type": "object",
        "properties": {
          "laureates": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "year": {
                  "type": "integer"
                },
                "name": {
                  "type": "string"
                },
                "kind": {
                  "type": "string",
                  "enum": [
                    "👤",
                    "🏛️"
                  ],
                  "description": "👤 for a person; 🏛️ for an organization or institution"
                },
                "country_code": {
                  "type": "string",
                  "description": "ISO 3166-1 alpha-2"
                },
                "motivation": {
                  "type": "string",
                  "description": "One-sentence citation summary"
                }
              },
              "required": [
                "year",
                "name",
                "kind",
                "country_code",
                "motivation"
              ],
              "additionalProperties": false
            }
          }
        },
        "required": [
          "laureates"
        ],
        "additionalProperties": false
      }
    }
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

const completion = await client.chat.completions.create({
  model: "subq-preview",
  messages: [
    {
      role: "system",
      content: "Return Nobel Peace Prize laureates for only the year range in the user message. One array entry per laureate (shared prizes produce multiple entries with the same year). Set kind to 👤 for a person and 🏛️ for an organization or institution. Use ISO 3166-1 alpha-2 country codes. Keep each motivation to one sentence."
    },
    {
      role: "user",
      content: "List Nobel Peace Prize winners from 2022 through 2024."
    }
  ],
  stream: false,
  response_format: {
    type: "json_schema",
    json_schema: {
      name: "nobel_peace_laureates",
      strict: true,
      schema: {
        type: "object",
        properties: {
          laureates: {
            type: "array",
            items: {
              type: "object",
              properties: {
                year: {
                  type: "integer"
                },
                name: {
                  type: "string"
                },
                kind: {
                  type: "string",
                  enum: [
                    "👤",
                    "🏛️"
                  ],
                  description: "👤 for a person; 🏛️ for an organization or institution"
                },
                country_code: {
                  type: "string",
                  description: "ISO 3166-1 alpha-2"
                },
                motivation: {
                  type: "string",
                  description: "One-sentence citation summary"
                }
              },
              required: [
                "year",
                "name",
                "kind",
                "country_code",
                "motivation"
              ],
              additionalProperties: false
            }
          }
        },
        required: [
          "laureates"
        ],
        additionalProperties: false
      }
    }
  }
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
            "content": "Return Nobel Peace Prize laureates for only the year range in the user message. One array entry per laureate (shared prizes produce multiple entries with the same year). Set kind to 👤 for a person and 🏛️ for an organization or institution. Use ISO 3166-1 alpha-2 country codes. Keep each motivation to one sentence.",
        },
        {
            "role": "user",
            "content": "List Nobel Peace Prize winners from 2022 through 2024.",
        },
    ],
    stream=False,
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "nobel_peace_laureates",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "laureates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "year": {
                                    "type": "integer",
                                },
                                "name": {
                                    "type": "string",
                                },
                                "kind": {
                                    "type": "string",
                                    "enum": [
                                        "👤",
                                        "🏛️",
                                    ],
                                    "description": "👤 for a person; 🏛️ for an organization or institution",
                                },
                                "country_code": {
                                    "type": "string",
                                    "description": "ISO 3166-1 alpha-2",
                                },
                                "motivation": {
                                    "type": "string",
                                    "description": "One-sentence citation summary",
                                },
                            },
                            "required": [
                                "year",
                                "name",
                                "kind",
                                "country_code",
                                "motivation",
                            ],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": [
                    "laureates",
                ],
                "additionalProperties": False,
            },
        },
    },
)

print(completion.choices[0].message.content)
```

The model returns schema-valid JSON as a string in `choices[0].message.content`.

Shown below after parsing (same shape either way — only the output location
differs, see [Field reference](#field-reference)):

```json
{
  "laureates": [
    {
      "year": 2022,
      "name": "Ales Bialiatski",
      "kind": "👤",
      "country_code": "BY",
      "motivation": "Recognized for his tireless efforts to expose human rights abuses and promote democracy in Belarus."
    },
    {
      "year": 2022,
      "name": "Memorial",
      "kind": "🏛️",
      "country_code": "RU",
      "motivation": "Honored for its documentation of political repression and human rights violations in the Soviet Union and Russia."
    },
    {
      "year": 2022,
      "name": "Center for Civil Liberties",
      "kind": "🏛️",
      "country_code": "UA",
      "motivation": "Commended for its courageous work defending human rights and civil liberties in Ukraine."
    },
    {
      "year": 2023,
      "name": "Narges Mohammadi",
      "kind": "👤",
      "country_code": "IR",
      "motivation": "Awarded for her unwavering fight against oppression and her advocacy for women's rights in Iran."
    },
    {
      "year": 2024,
      "name": "Nihon Hidankyo",
      "kind": "🏛️",
      "country_code": "JP",
      "motivation": "Recognized for its efforts to achieve a world free of nuclear weapons and its work to eliminate nuclear weapons."
    }
  ]
}
```

| Field          | Type    | Notes                               |
| -------------- | ------- | ----------------------------------- |
| `laureates`    | array   | One object per laureate             |
| `year`         | integer | Award year                          |
| `name`         | string  | Person or organization              |
| `kind`         | enum    | `👤` individual, `🏛️` organization |
| `country_code` | string  | ISO 3166-1 alpha-2                  |
| `motivation`   | string  | One-sentence citation summary       |

Set `stream` to `false` or omit it for a single JSON response.

## Response handling

Parse the JSON string at the output location from the [field reference](#field-reference) above. Before parsing, check for HTTP 4xx errors, refusals/incomplete status, and truncation, then validate the parsed JSON in your app.

### Handling edge cases (Responses API)

```ts title="TypeScript"
import OpenAI from "openai";

const nobelSchema = {
  type: "object",
  properties: {
    laureates: {
      type: "array",
      items: {
        type: "object",
        properties: {
          year: { type: "integer" },
          name: { type: "string" },
        },
        required: ["year", "name"],
        additionalProperties: false,
      },
    },
  },
  required: ["laureates"],
  additionalProperties: false,
};

const client = new OpenAI({
  apiKey: process.env.SUBQ_API_KEY,
  baseURL: "https://api.subq.ai/v1",
  maxRetries: 0,
});

let laureates;
try {
  const response = await client.responses.create({
    model: "subq-preview",
    input: "List Nobel Peace Prize winners from 2024.",
    text: {
      format: {
        type: "json_schema",
        name: "nobel_peace_laureates",
        strict: true,
        schema: nobelSchema,
      },
    },
  });

  // @check truncated — status is not "completed", or incomplete_details is set
  if (response.status !== "completed" || response.incomplete_details) {
    throw new Error(`Response did not complete: ${response.status}`);
  }

  const message = response.output.find((item) => item.type === "message");
  const text = message?.content
    ?.filter((part) => part.type === "output_text")
    .map((part) => part.text)
    .join("");

  if (!text) {
    throw new Error("Missing assistant text.");
  }

  // @check parse — content is a JSON string at output[].content[].text
  const data = JSON.parse(text);

  // @check validate — schema-valid JSON; verify meaning in your app
  laureates = data.laureates;
} catch (error) {
  // @check bad-request — HTTP 4xx + error (no response)
  if (error instanceof OpenAI.APIError) throw error;
  throw error;
}
```

```py title="Python"
import json
import os

from openai import APIError, OpenAI

nobel_schema = {
    "type": "object",
    "properties": {
        "laureates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer"},
                    "name": {"type": "string"},
                },
                "required": ["year", "name"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["laureates"],
    "additionalProperties": False,
}

client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
    max_retries=0,
)

try:
    response = client.responses.create(
        model="subq-preview",
        input="List Nobel Peace Prize winners from 2024.",
        text={
            "format": {
                "type": "json_schema",
                "name": "nobel_peace_laureates",
                "strict": True,
                "schema": nobel_schema,
            },
        },
    )
except APIError:
    # @check bad-request — HTTP 4xx + error (no response)
    raise

# @check truncated — status is not "completed", or incomplete_details is set
if response.status != "completed" or response.incomplete_details:
    raise RuntimeError(f"Response did not complete: {response.status}")

message = next((item for item in response.output if item.type == "message"), None)
text = "".join(
    part.text for part in (message.content if message else []) if part.type == "output_text"
)

if not text:
    raise RuntimeError("Missing assistant text.")

# @check parse — content is a JSON string at output[].content[].text
data = json.loads(text)

# @check validate — schema-valid JSON; verify meaning in your app
laureates = data["laureates"]
```

### Handling edge cases (Chat Completions)

```ts title="TypeScript"
import OpenAI from "openai";

const nobelSchema = {
  type: "object",
  properties: {
    laureates: {
      type: "array",
      items: {
        type: "object",
        properties: {
          year: { type: "integer" },
          name: { type: "string" },
        },
        required: ["year", "name"],
        additionalProperties: false,
      },
    },
  },
  required: ["laureates"],
  additionalProperties: false,
};

const client = new OpenAI({
  apiKey: process.env.SUBQ_API_KEY,
  baseURL: "https://api.subq.ai/v1",
  maxRetries: 0,
});

let laureates;
try {
  const completion = await client.chat.completions.create({
    model: "subq-preview",
    messages: [
      { role: "user", content: "List Nobel Peace Prize winners from 2024." },
    ],
    response_format: {
      type: "json_schema",
      json_schema: {
        name: "nobel_peace_laureates",
        strict: true,
        schema: nobelSchema,
      },
    },
  });

  const choice = completion.choices[0];
  const message = choice?.message;

  // @check refusal — choices[0].message.refusal
  if (message?.refusal) {
    throw new Error(`Refused: ${message.refusal}`);
  }

  // @check truncated — finish_reason is "length"
  if (choice?.finish_reason === "length") {
    throw new Error("Response truncated; increase max_tokens or narrow the schema.");
  }

  if (!message?.content) {
    throw new Error("Missing assistant content.");
  }

  // @check parse — content is a JSON string in choices[0].message.content
  const data = JSON.parse(message.content);

  // @check validate — schema-valid JSON; verify meaning in your app
  laureates = data.laureates;
} catch (error) {
  // @check bad-request — HTTP 4xx + error (no completion)
  if (error instanceof OpenAI.APIError) throw error;
  throw error;
}
```

```py title="Python"
import json
import os

from openai import APIError, OpenAI

nobel_schema = {
    "type": "object",
    "properties": {
        "laureates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer"},
                    "name": {"type": "string"},
                },
                "required": ["year", "name"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["laureates"],
    "additionalProperties": False,
}

client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
    max_retries=0,
)

try:
    completion = client.chat.completions.create(
        model="subq-preview",
        messages=[
            {"role": "user", "content": "List Nobel Peace Prize winners from 2024."},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "nobel_peace_laureates",
                "strict": True,
                "schema": nobel_schema,
            },
        },
    )
except APIError:
    # @check bad-request — HTTP 4xx + error (no completion)
    raise

choice = completion.choices[0]
message = choice.message

# @check refusal — choices[0].message.refusal
if getattr(message, "refusal", None):
    raise RuntimeError(f"Refused: {message.refusal}")

# @check truncated — finish_reason is "length"
if choice.finish_reason == "length":
    raise RuntimeError("Response truncated; increase max_tokens or narrow the schema.")

if not message.content:
    raise RuntimeError("Missing assistant content.")

# @check parse — content is a JSON string in choices[0].message.content
data = json.loads(message.content)

# @check validate — schema-valid JSON; verify meaning in your app
laureates = data["laureates"]
```

## Best practices

- **Use the system message (or `instructions`) to interpret the schema.** The schema sets shape; the system prompt sets meaning. Spell out formats, enums, and terse field names—the example above does this.
- **Define fallbacks for missing data.** Required fields still need a value when input omits them—e.g. "use 0 for exposure\_usd when not applicable."
- **Keep schemas small.** Flat objects are easier to satisfy than deep nesting.

## Related

- [Responses API](/endpoints/responses-api/#structured-outputs) — structured output via `text.format`.
- [Chat Completions API](/endpoints/chat-completions-api/) — request fields and response shape.
- [Decisions API](/endpoints/decisions-api/) — yes/no, choice, and score judgments with probabilities.
- [Function calling](/using-the-api/function-calling/) — tools and tool call outputs.
- [Models](/using-the-api/models/) — supported model IDs.
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) — full feature reference.
