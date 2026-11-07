---
title: Files API
description: Upload, list, retrieve, and delete org-scoped files for use with Chat Completions and Responses.
---

> Status: Early access

Use the Files API to upload and manage documents for your organization. Files are
org-scoped — a file is only visible to the organization that created it.

After upload, reference a file by `file_id`: a `file` part on
[Chat Completions](/endpoints/chat-completions-api/), or an `input_file` part on
the [Responses API](/endpoints/responses-api/). See [Sending files](/using-the-api/file-inputs/)
for the request shapes and for when to upload rather than inline a document.

## Endpoints

| Method   | Path                  | Description               |
| -------- | --------------------- | ------------------------- |
| `POST`   | `/v1/files`           | Upload a file (multipart) |
| `GET`    | `/v1/files`           | List the org's files      |
| `GET`    | `/v1/files/{file_id}` | Retrieve one file         |
| `DELETE` | `/v1/files/{file_id}` | Delete a file             |

## Limits

- **Max size:** 50 MiB per file.
- **Purpose:** `assistants` (only value accepted today).
- **Supported types:** plain text (`.txt`, `.md`, `.csv`, `.tsv`), JSON / JSONL,
  XML, PDF, and Word (`.doc`, `.docx`).

## File object

| Field        | Type           | Description                                                                    |
| ------------ | -------------- | ------------------------------------------------------------------------------ |
| `id`         | string         | File identifier (`file_…`). Use as `file_id` in Chat Completions or Responses. |
| `object`     | string         | Always `"file"`.                                                               |
| `bytes`      | number         | Size in bytes.                                                                 |
| `created_at` | number         | Unix timestamp (seconds) when the file was created.                            |
| `expires_at` | number or null | Expiration timestamp, if any.                                                  |
| `filename`   | string         | Original file name.                                                            |
| `purpose`    | string         | Intended purpose (`assistants`).                                               |
| `status`     | string or null | Lifecycle status (see below).                                                  |

### Statuses

| Status      | Meaning                                                                                  |
| ----------- | ---------------------------------------------------------------------------------------- |
| `uploaded`  | Bytes stored and validated. Non-text files may still be extracting text.                 |
| `processed` | Content available for Chat Completions and Responses. Text files reach this immediately. |
| `error`     | Text extraction failed. A later retry can flip it back to `processed`.                   |

## Upload file

```
POST /v1/files
```

Upload bytes through the API as `multipart/form-data`.

| Field     | Required | Description           |
| --------- | -------- | --------------------- |
| `file`    | Yes      | The file part.        |
| `purpose` | Yes      | Must be `assistants`. |

The `file` part must carry a `Content-Type` from the [supported types](#limits).
A part sent as `application/octet-stream` is rejected with `unsupported_file_type`,
so set the type explicitly when your HTTP client does not infer it from the
filename — as the TypeScript example below does with `toFile()`.

```bash title="cURL"
curl --request POST \
  --url https://api.subq.ai/v1/files \
  --header "Authorization: Bearer $SUBQ_API_KEY" \
  --form purpose=assistants \
  --form file='@./report.pdf'
```

```ts title="TypeScript"
import { createReadStream } from "node:fs";
import OpenAI, { toFile } from "openai";

const client = new OpenAI({
  apiKey: process.env.SUBQ_API_KEY,
  baseURL: "https://api.subq.ai/v1",
});

const file = await client.files.create({
  file: await toFile(createReadStream("./report.pdf"), "report.pdf", {
    type: "application/pdf",
  }),
  purpose: "assistants",
});

console.log(file.id);
```

```py title="Python"
client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
)

with open("./report.pdf", "rb") as handle:
    file = client.files.create(file=handle, purpose="assistants")

print(file.id)
```

### Response

```json
{
  "id": "file_abc123",
  "object": "file",
  "bytes": 12345,
  "created_at": 1753742400,
  "expires_at": null,
  "filename": "report.pdf",
  "purpose": "assistants",
  "status": "uploaded"
}
```

### Uploading multiple files

Each request uploads one file — call the endpoint once per file and run the
calls concurrently rather than looping with `await` one at a time:

```ts title="TypeScript"
import { createReadStream } from "node:fs";
import OpenAI, { toFile } from "openai";

const client = new OpenAI({
  apiKey: process.env.SUBQ_API_KEY,
  baseURL: "https://api.subq.ai/v1",
});

async function uploadFile(path: string, contentType: string) {
  return client.files.create({
    file: await toFile(createReadStream(path), path.split("/").pop(), {
      type: contentType,
    }),
    purpose: "assistants",
  });
}

// Each request uploads one file — fire the calls concurrently rather than
// looping with `await` one at a time.
const uploads = [
  { path: "./report.pdf", contentType: "application/pdf" },
  { path: "./meeting-notes.txt", contentType: "text/plain" },
];
const files = await Promise.all(
  uploads.map(({ path, contentType }) => uploadFile(path, contentType)),
);

files.forEach((file, i) => console.log(`${uploads[i].path} -> ${file.id}`));
```

```py title="Python"
import asyncio
import os

from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
)


async def upload_file(path):
    with open(path, "rb") as handle:
        return await client.files.create(file=handle, purpose="assistants")


async def upload_multiple(paths):
    # Each request uploads one file — gather the calls concurrently rather
    # than awaiting one at a time.
    return await asyncio.gather(*(upload_file(path) for path in paths))


paths = ["./report.pdf", "./meeting-notes.txt"]
files = asyncio.run(upload_multiple(paths))
for path, file in zip(paths, files):
    print(f"{path} -> {file.id}")
```

## List files

```
GET /v1/files
```

| Param     | Type    | Default | Description                              |
| --------- | ------- | ------- | ---------------------------------------- |
| `limit`   | integer | `20`    | Page size (`1`–`10000`).                 |
| `order`   | string  | `desc`  | Sort by creation time: `asc` or `desc`.  |
| `after`   | string  | —       | Keyset cursor; start after this file id. |
| `purpose` | string  | —       | Optional filter (`assistants`).          |

```bash title="cURL"
curl --request GET \
  --url 'https://api.subq.ai/v1/files?limit=20&order=desc' \
  --header "Authorization: Bearer $SUBQ_API_KEY"
```

```ts title="TypeScript"
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.SUBQ_API_KEY,
  baseURL: "https://api.subq.ai/v1",
});

const files = await client.files.list({ limit: 20, order: "desc" });

console.log(files.data);
```

```py title="Python"
client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
)

files = client.files.list(limit=20, order="desc")

print(files.data)
```

### Response

```json
{
  "object": "list",
  "data": [
    {
      "id": "file_abc123",
      "object": "file",
      "bytes": 12345,
      "created_at": 1753742400,
      "expires_at": null,
      "filename": "report.pdf",
      "purpose": "assistants",
      "status": "processed"
    }
  ],
  "first_id": "file_abc123",
  "last_id": "file_abc123",
  "has_more": false
}
```

Paginate with `last_id` as the next `after` value until `has_more` is `false`.

## Retrieve file

```
GET /v1/files/{file_id}
```

```bash title="cURL"
curl --request GET \
  --url https://api.subq.ai/v1/files/file_abc123 \
  --header "Authorization: Bearer $SUBQ_API_KEY"
```

```ts title="TypeScript"
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.SUBQ_API_KEY,
  baseURL: "https://api.subq.ai/v1",
});

const file = await client.files.retrieve(process.env.SUBQ_FILE_ID ?? "file_abc123");

console.log(file);
```

```py title="Python"
client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
)

file = client.files.retrieve(os.getenv("SUBQ_FILE_ID", "file_abc123"))

print(file)
```

Returns the File object, or `404` if missing or owned by another org.

## Delete file

```
DELETE /v1/files/{file_id}
```

Removes stored bytes and metadata.

```bash title="cURL"
curl --request DELETE \
  --url https://api.subq.ai/v1/files/file_abc123 \
  --header "Authorization: Bearer $SUBQ_API_KEY"
```

```ts title="TypeScript"
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.SUBQ_API_KEY,
  baseURL: "https://api.subq.ai/v1",
});

const result = await client.files.delete(process.env.SUBQ_FILE_ID ?? "file_abc123");

console.log(result.deleted);
```

```py title="Python"
client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
)

result = client.files.delete(os.getenv("SUBQ_FILE_ID", "file_abc123"), extra_body={})

print(result.deleted)
```

### Response

```json
{
  "id": "file_abc123",
  "object": "file",
  "deleted": true
}
```

## Errors

Errors use the OpenAI shape:

```json
{
  "error": {
    "message": "No such File object: file_abc123",
    "type": "invalid_request_error",
    "code": "not_found",
    "param": null
  }
}
```

| HTTP  | `code`                  | When                                  |
| ----- | ----------------------- | ------------------------------------- |
| `400` | `validation_error`      | Missing or invalid params             |
| `400` | `unsupported_file_type` | MIME type not in the supported set    |
| `401` | `invalid_api_key`       | Missing or invalid API key            |
| `403` | `org_suspended`         | Organization is suspended or inactive |
| `404` | `not_found`             | File missing or owned by another org  |
| `413` | `file_too_large`        | Upload exceeds 50 MiB                 |

## Related

- [Sending files](/using-the-api/file-inputs/) — referencing an uploaded file in a request
- [Chat Completions API](/endpoints/chat-completions-api/) — `file` parts on `messages`
- [Responses API](/endpoints/responses-api/) — `input_file` parts on `input`
- [Authentication](/using-the-api/authentication/) — API keys
