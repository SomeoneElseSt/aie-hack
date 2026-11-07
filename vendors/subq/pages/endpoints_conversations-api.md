---
title: Conversations API
description: Manage conversation history as a stored resource — create, retrieve, update, delete, and manage the items inside it.
---

> Status: Early access

Use the Conversations API to create, inspect, retag, and delete stored
conversations — and the items inside them. How long that history stays is
covered in [Data retention](/using-the-api/data-retention/). These are storage
operations — no inference runs. Continue a conversation directly from `/v1/responses`
with the [`conversation`](/endpoints/responses-api/#request-body) field, or
without a stored resource at all via
[`previous_response_id`](/endpoints/responses-api/#multi-turn-conversations).

## Endpoints

| Method   | Path                                                  | Description                      |
| -------- | ----------------------------------------------------- | -------------------------------- |
| `POST`   | `/v1/conversations`                                   | Create a conversation            |
| `GET`    | `/v1/conversations/{conversation_id}`                 | Retrieve a conversation          |
| `POST`   | `/v1/conversations/{conversation_id}`                 | Update a conversation's metadata |
| `DELETE` | `/v1/conversations/{conversation_id}`                 | Delete a conversation            |
| `POST`   | `/v1/conversations/{conversation_id}/items`           | Add items to a conversation      |
| `GET`    | `/v1/conversations/{conversation_id}/items`           | List a conversation's items      |
| `GET`    | `/v1/conversations/{conversation_id}/items/{item_id}` | Retrieve an item                 |
| `DELETE` | `/v1/conversations/{conversation_id}/items/{item_id}` | Delete an item                   |

## The conversation object

Every endpoint except delete returns a conversation object:

```json
{
  "id": "conv_abc123",
  "object": "conversation",
  "created_at": 1751484000,
  "metadata": { "department": "cardiology", "acuity": "unconfirmed" }
}
```

| Field        | Type    | Description                                                                                                                          |
| ------------ | ------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `id`         | string  | Conversation ID (`conv_...`).                                                                                                        |
| `object`     | string  | Always `"conversation"`.                                                                                                             |
| `created_at` | integer | Unix timestamp (seconds) of creation. Unchanged on update.                                                                           |
| `metadata`   | object  | String-to-string tags. Always an object (`{}` if untagged, never `null`). Up to 16 keys; keys up to 64 characters, values up to 512. |

## Create a conversation

```
POST /v1/conversations
```

All fields are optional. An empty body creates an untagged conversation.

```bash title="cURL"
curl --request POST \
  --url https://api.subq.ai/v1/conversations \
  --header "Authorization: Bearer $SUBQ_API_KEY" \
  --header 'Content-Type: application/json' \
  --data '
{
  "metadata": {
    "department": "cardiology",
    "acuity": "unconfirmed"
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

const conversation = await client.conversations.create({
  metadata: { department: "cardiology", acuity: "unconfirmed" },
});

console.log(conversation.id);
```

```py title="Python"
client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
)

conversation = client.conversations.create(
    metadata={"department": "cardiology", "acuity": "unconfirmed"},
)

print(conversation.id)
```

Seed it with prior history by passing `items` — up to 20 user messages, text only (see [Items](#items) to add more later):

```json
{
  "metadata": { "department": "cardiology" },
  "items": [
    { "role": "user", "content": "Patient reports chest pain since this morning." }
  ]
}
```

Orgs configured for [zero data retention](/using-the-api/data-retention/#zero-data-retention)
cannot create conversations (`403` `zero_data_retention`). Send the full
input on each `/v1/responses` request instead.

## Retrieve a conversation

```
GET /v1/conversations/{conversation_id}
```

```bash title="cURL"
curl --request GET \
  --url https://api.subq.ai/v1/conversations/conv_abc123 \
  --header "Authorization: Bearer $SUBQ_API_KEY"
```

```ts title="TypeScript"
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.SUBQ_API_KEY,
  baseURL: "https://api.subq.ai/v1",
});

const conversation = await client.conversations.retrieve(
  process.env.SUBQ_CONVERSATION_ID ?? "conv_abc123",
);

console.log(conversation.metadata);
```

```py title="Python"
client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
)

conversation = client.conversations.retrieve(
    os.getenv("SUBQ_CONVERSATION_ID", "conv_abc123")
)

print(conversation.metadata)
```

Returns the [conversation object](#the-conversation-object). An unknown id,
or one that belongs to another organization, returns `404`
`conversation_not_found`.

## Update a conversation

```
POST /v1/conversations/{conversation_id}
```

`metadata` is required and **replaces** the stored tags. Resend every key
you want to keep; send `{}` to clear them.

```bash title="cURL"
curl --request POST \
  --url https://api.subq.ai/v1/conversations/conv_abc123 \
  --header "Authorization: Bearer $SUBQ_API_KEY" \
  --header 'Content-Type: application/json' \
  --data '
{
  "metadata": {
    "department": "cardiology",
    "acuity": "urgent"
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

// metadata replaces the stored tags entirely — resend every key you want to keep.
const conversation = await client.conversations.update(
  process.env.SUBQ_CONVERSATION_ID ?? "conv_abc123",
  { metadata: { department: "cardiology", acuity: "urgent" } },
);

console.log(conversation.metadata);
```

```py title="Python"
client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
)

# metadata replaces the stored tags entirely — resend every key you want to keep.
conversation = client.conversations.update(
    os.getenv("SUBQ_CONVERSATION_ID", "conv_abc123"),
    metadata={"department": "cardiology", "acuity": "urgent"},
)

print(conversation.metadata)
```

## Delete a conversation

```
DELETE /v1/conversations/{conversation_id}
```

Deletes the conversation and every [item](#items) and response in it. Irreversible.

```bash title="cURL"
curl --request DELETE \
  --url https://api.subq.ai/v1/conversations/conv_abc123 \
  --header "Authorization: Bearer $SUBQ_API_KEY"
```

```ts title="TypeScript"
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.SUBQ_API_KEY,
  baseURL: "https://api.subq.ai/v1",
});

const result = await client.conversations.delete(
  process.env.SUBQ_CONVERSATION_ID ?? "conv_abc123",
);

console.log(result.deleted);
```

```py title="Python"
client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
)

result = client.conversations.delete(
    os.getenv("SUBQ_CONVERSATION_ID", "conv_abc123")
)

print(result.deleted)
```

```json
{
  "id": "conv_abc123",
  "object": "conversation.deleted",
  "deleted": true
}
```

## Items

List, add, retrieve, or delete the individual messages, function calls, and
web searches inside a conversation.

| Method   | Path                                                  | Description      |
| -------- | ----------------------------------------------------- | ---------------- |
| `POST`   | `/v1/conversations/{conversation_id}/items`           | Add items        |
| `GET`    | `/v1/conversations/{conversation_id}/items`           | List items       |
| `GET`    | `/v1/conversations/{conversation_id}/items/{item_id}` | Retrieve an item |
| `DELETE` | `/v1/conversations/{conversation_id}/items/{item_id}` | Delete an item   |

Add items the same way you [seed a conversation](#create-a-conversation) —
`role: "user"`, text only:

```json
{
  "items": [
    { "role": "user", "content": "Follow-up: any allergies on file?" }
  ]
}
```

Reasoning and function-call outputs aren't individually addressable — they
stay attached to their parent message, unlike OpenAI's API. List paginates
with `limit` (1–100, default 20), `order`, and an `after` cursor, same as
[Files](/endpoints/files-api/#list-files). Delete returns the parent
conversation object, not a deletion envelope.

## Errors

```json
{
  "error": {
    "message": "Conversation 'conv_abc123' not found.",
    "type": "invalid_request_error",
    "code": "conversation_not_found"
  }
}
```

| HTTP | `code`                   | Meaning                                                                   |
| ---- | ------------------------ | ------------------------------------------------------------------------- |
| 401  | `invalid_api_key`        | Missing or invalid Bearer token                                           |
| 404  | `conversation_not_found` | Id doesn't exist or belongs to another organization                       |
| 404  | `item_not_found`         | Item doesn't exist in the conversation, or isn't individually addressable |
| 403  | `zero_data_retention`    | Org cannot store conversations                                            |
| 403  | `access_denied`          | API key does not belong to an organization                                |
| 503  | `authorization_failed`   | Key lookup temporarily unavailable; retry                                 |

See [Authentication](/using-the-api/authentication/) for auth and credit errors.

## Related

- [Responses API](/endpoints/responses-api/) — continue a stored conversation directly with the `conversation` field, or chain turns with `previous_response_id`; every response includes a `conversation` field either way.
- [Authentication](/using-the-api/authentication/) — API keys and request headers.
