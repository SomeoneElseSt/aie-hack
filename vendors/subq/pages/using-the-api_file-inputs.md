---
title: Sending files
description: Send documents inline as base64, or upload once and reference them by file_id on Chat Completions or Responses.
---

> Status: Early access

Upload a file once via the [Files API](/endpoints/files-api/) and reference it by `file_id` on Chat Completions or Responses, or send it inline — base64-encoded directly in the request — on Chat Completions only.

## Field reference

|               | Responses API        | Chat Completions |
| ------------- | -------------------- | ---------------- |
| Part type     | `input_file`         | `file`           |
| Inline base64 | Not supported        | `file_data`      |
| Uploaded file | `file_id` (required) | `file_id`        |

## Inline base64

Inline `file_data` is Chat Completions only. Include a text part with your instruction, then one or more `file` parts for the documents.

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
      "content": [
        {
          "type": "text",
          "text": "Summarize these documents."
        },
        {
          "type": "file",
          "filename": "financial-report-2026.pdf",
          "mime_type": "application/pdf",
          "file_data": "JVBERi0xLjcKJdDUxdgK..."
        },
        {
          "type": "file",
          "filename": "board-deck-q1.pdf",
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

const financialSummary = Buffer.from("Quarterly revenue was $4.2M.\n").toString(
  "base64",
);
const meetingNotes = Buffer.from(
  "Follow up with legal on the updated MSA template.\n",
).toString("base64");

const completion = await client.chat.completions.create({
  model: "subq-preview",
  messages: [
    {
      role: "user",
      content: [
        { type: "text", text: "Summarize these documents." },
        {
          type: "file",
          filename: "financial-summary.txt",
          mime_type: "text/plain",
          file_data: financialSummary,
        },
        {
          type: "file",
          filename: "meeting-notes.txt",
          mime_type: "text/plain",
          file_data: meetingNotes,
        },
      ],
    },
  ],
});

console.log(completion.choices[0].message.content);
```

```py title="Python"
import base64
import os

from openai import OpenAI

client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
)

financial_summary = base64.b64encode(b"Quarterly revenue was $4.2M.\n").decode("ascii")
meeting_notes = base64.b64encode(
    b"Follow up with legal on the updated MSA template.\n"
).decode("ascii")

completion = client.chat.completions.create(
    model="subq-preview",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Summarize these documents."},
                {
                    "type": "file",
                    "filename": "financial-summary.txt",
                    "mime_type": "text/plain",
                    "file_data": financial_summary,
                },
                {
                    "type": "file",
                    "filename": "meeting-notes.txt",
                    "mime_type": "text/plain",
                    "file_data": meeting_notes,
                },
            ],
        }
    ],
)

print(completion.choices[0].message.content)
```

Set `file_data` to the base64-encoded file content — plain, with no line wrapping. Do not use a data URL prefix such as `data:application/pdf;base64,`.

### cURL with files

Use `openssl base64 -A` to inline local files without line wrapping. For remote files, download them first (for example with `curl -fsS -o /tmp/report.pdf <url>`), then base64-encode the local file as shown below. Avoid piping a remote download directly into the request body.

```bash
curl -sS -X POST https://api.subq.ai/v1/chat/completions \
  -H "Authorization: Bearer $SUBQ_API_KEY" \
  -H "Content-Type: application/json" \
  --data-binary @- <<EOF
{"model":"subq-preview","messages":[{"role":"user","content":[
{"type":"text","text":"Summarize these documents."},
{"type":"file","filename":"financial-report-2026.pdf","mime_type":"application/pdf","file_data":"$(openssl base64 -A -in /tmp/financial-report-2026.pdf)"},
{"type":"file","filename":"board-deck-q1.pdf","mime_type":"application/pdf","file_data":"$(openssl base64 -A -in /tmp/board-deck-q1.pdf)"},
{"type":"file","filename":"meeting-notes.txt","mime_type":"text/plain","file_data":"$(openssl base64 -A -in /tmp/meeting-notes.txt)"}
]}],"stream":false}
EOF
```

### File part

| Field       | Type   | Required | Description                                                                                                        |
| ----------- | ------ | -------- | ------------------------------------------------------------------------------------------------------------------ |
| `type`      | string | Yes      | Must be `"file"`.                                                                                                  |
| `filename`  | string | No       | Recommended. File name to associate with the document, such as `financial-report-2026.pdf` or `meeting-notes.txt`. |
| `mime_type` | string | Yes      | MIME type for the file, such as `"application/pdf"` or `"text/plain"`.                                             |
| `file_data` | string | Yes      | Base64-encoded file content.                                                                                       |

### Accepted file types

Set `mime_type` to match the file you send.

| Category   | Extensions | MIME type                       |
| ---------- | ---------- | ------------------------------- |
| PDF        | `.pdf`     | `application/pdf`               |
| Plain text | `.txt`     | `text/plain`                    |
| Markdown   | `.md`      | `text/markdown`                 |
| CSV        | `.csv`     | `text/csv`                      |
| TSV        | `.tsv`     | `text/tab-separated-values`     |
| JSON       | `.json`    | `application/json`              |
| XML        | `.xml`     | `application/xml` or `text/xml` |

Word (`.doc`/`.docx`) and JSONL aren't accepted inline — upload them and pass `file_id` instead. See [Files API](/endpoints/files-api/#limits) for the full uploaded-file format list.

## Uploaded files

Upload the document once, then pass the id it returns as `file_id`. Reference more than one document by adding a part per file. Responses uses `input_file` parts; Chat Completions uses `file` parts.

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
      "type": "input_file",
      "file_id": "file_def456"
    },
    {
      "type": "input_text",
      "text": "Summarize these documents."
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

const fileId1 = process.env.SUBQ_FILE_ID ?? "file_abc123";
const fileId2 = process.env.SUBQ_FILE_ID_2 ?? "file_def456";

const response = await client.responses.create({
  model: "subq-preview",
  input: [
    { type: "input_file", file_id: fileId1 },
    { type: "input_file", file_id: fileId2 },
    { type: "input_text", text: "Summarize these documents." },
  ],
});

const message = response.output.find((item) => item.type === "message");
const text = message?.content
  ?.filter((part) => part.type === "output_text")
  .map((part) => part.text)
  .join("");

console.log(text);
```

```py title="Python"
import os

from openai import OpenAI

client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
)

file_id_1 = os.getenv("SUBQ_FILE_ID", "file_abc123")
file_id_2 = os.getenv("SUBQ_FILE_ID_2", "file_def456")

response = client.responses.create(
    model="subq-preview",
    input=[
        {"type": "input_file", "file_id": file_id_1},
        {"type": "input_file", "file_id": file_id_2},
        {"type": "input_text", "text": "Summarize these documents."},
    ],
)

message = next((item for item in response.output if item.type == "message"), None)
text = "".join(
    part.text for part in (message.content if message else []) if part.type == "output_text"
)

print(text)
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
      "content": [
        {
          "type": "text",
          "text": "Summarize these documents."
        },
        {
          "type": "file",
          "file_id": "file_abc123"
        },
        {
          "type": "file",
          "file_id": "file_def456"
        }
      ]
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

const fileId1 = process.env.SUBQ_FILE_ID ?? "file_abc123";
const fileId2 = process.env.SUBQ_FILE_ID_2 ?? "file_def456";

const completion = await client.chat.completions.create({
  model: "subq-preview",
  messages: [
    {
      role: "user",
      content: [
        { type: "text", text: "Summarize these documents." },
        { type: "file", file_id: fileId1 },
        { type: "file", file_id: fileId2 },
      ],
    },
  ],
});

console.log(completion.choices[0].message.content);
```

```py title="Python"
import os

from openai import OpenAI

client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
)

file_id_1 = os.getenv("SUBQ_FILE_ID", "file_abc123")
file_id_2 = os.getenv("SUBQ_FILE_ID_2", "file_def456")

completion = client.chat.completions.create(
    model="subq-preview",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Summarize these documents."},
                {"type": "file", "file_id": file_id_1},
                {"type": "file", "file_id": file_id_2},
            ],
        }
    ],
)

print(completion.choices[0].message.content)
```

Non-text formats need to finish processing first — wait for `status` to reach `processed` before referencing them. See [Files API](/endpoints/files-api/) for upload mechanics, visibility, and the rest of the file lifecycle. Responses does not accept inline `file_data`; see [Responses input](/endpoints/responses-api/#uploaded-files-file_id).

## Choosing an approach

|                  | Inline base64                                                                                                   | Uploaded file                           |
| ---------------- | --------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| Sent as          | `file_data` on the request                                                                                      | `file_id` from an earlier upload        |
| Extra request    | None                                                                                                            | `POST /v1/files` once per file          |
| Reuse            | Re-sends the bytes every time                                                                                   | Reference the same `file_id` repeatedly |
| Accepted formats | PDF, plain text, Markdown, CSV, TSV, JSON, and XML                                                              | Adds JSONL and Word (`.doc`/`.docx`)    |
| Size             | 25 MiB for the whole request, base64 included (about 18 MiB of files in total); larger requests fail with `413` | 50 MiB per file                         |
| Lifetime         | Prompt and completion: 60 days. PDFs: no expiry unless `store: false`                                           | Kept until you delete it                |

See [Data retention](/using-the-api/data-retention/) for what is stored and how to delete it.

Inline base64 is the shortest path for a one-off Chat Completions request. Upload the file instead when you are calling Responses, when the same document is used across several requests, when it is large, or when it is a format inline input does not accept.

## Response handling

Once a file's `status` is `processed`, its content is available to the model for that request — the reply is ordinary assistant text, the same as any other turn. Combine with [Structured outputs](/using-the-api/structured-outputs/) to extract specific fields from the document instead of a free-text summary.

## Related

- [Files API](/endpoints/files-api/) — upload, list, retrieve, and delete stored files.
- [Chat Completions API](/endpoints/chat-completions-api/) — `file` parts on `messages`.
- [Responses API](/endpoints/responses-api/) — `input_file` parts on `input`.
- [Models](/using-the-api/models/) — supported model IDs.
