---
title: Decisions API
description: Turn text or structured state into typed decisions with probabilities and confidence.
---

> Status: Public preview

Use the Decisions API for fast, structured judgments rather than generated
text. It evaluates a `state` and optional images, then returns typed answers and
probabilities your code can use directly.

```text
POST /v1/systemone
```

For text generation, use [`subq-preview`](/using-the-api/models/#subq-preview) (Early access)
on [Chat Completions](/endpoints/chat-completions-api/) or
[Responses](/endpoints/responses-api/).
[Request access](https://subq.ai/small#waitlist).

## Make a decision

```bash title="cURL"
curl --request POST \
  --url https://api.subq.ai/v1/systemone \
  --header "Authorization: Bearer $SUBQ_API_KEY" \
  --header 'Content-Type: application/json' \
  --data @- <<'EOF'
{
  "model": "subq-snap-1.1",
  "state": "Patient with asthma reports a sore throat, fever since yesterday, and shortness of breath walking to the kitchen this morning.",
  "questions": {
    "escalate": {
      "type": "noul",
      "instructions": "Should a nurse see this chat before the patient books anything?",
      "criteria": {
        "true": "Breathing trouble, chest pain, or a flare of a known condition",
        "false": "Stable symptoms the patient can book for themselves"
      }
    },
    "queue": {
      "type": "choice",
      "instructions": "Which team should own this chat?",
      "criteria": {
        "nurse_line": "Needs a nurse to assess symptoms today",
        "primary_care": "Book with the patient's own doctor",
        "pharmacy": "Refill or medication question only",
        "front_desk": null
      }
    },
    "acuity": {
      "type": "score",
      "instructions": "How soon should someone respond?",
      "criteria": [
        "Within a week",
        "Within a day",
        "Within an hour"
      ]
    }
  }
}
EOF
```

```ts title="TypeScript"
const baseURL = "https://api.subq.ai/v1";

// The text to judge.
const state =
  "Patient with asthma reports a sore throat, fever since yesterday, and shortness of breath walking to the kitchen this morning.";

// One question per judgment: a yes/no gate, an owning team, a response time.
const questions = {
  escalate: {
    type: "noul",
    instructions: "Should a nurse see this chat before the patient books anything?",
    criteria: {
      true: "Breathing trouble, chest pain, or a flare of a known condition",
      false: "Stable symptoms the patient can book for themselves",
    },
  },
  queue: {
    type: "choice",
    instructions: "Which team should own this chat?",
    criteria: {
      nurse_line: "Needs a nurse to assess symptoms today",
      primary_care: "Book with the patient's own doctor",
      pharmacy: "Refill or medication question only",
      front_desk: null,
    },
  },
  acuity: {
    type: "score",
    instructions: "How soon should someone respond?",
    criteria: ["Within a week", "Within a day", "Within an hour"],
  },
};

const response = await fetch(`${baseURL}/systemone`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${process.env.SUBQ_API_KEY}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    model: "subq-snap-1.1",
    state,
    questions,
  }),
});

if (!response.ok) {
  const error = await response.json();
  throw new Error(
    `${response.status} ${error.detail.error_type}: ${error.detail.message}`,
  );
}

const result = await response.json();
const { escalate, queue, acuity } = result.answers;

// Your code decides what happens next. Unsure routing goes to a nurse,
// and so does anything the gate says needs one.
let owner = queue.confidence >= 0.6 ? queue.choice : "nurse_line";
if (escalate.noul >= 0.5) owner = "nurse_line";

const respondWithin = acuity.legend[String(Math.round(acuity.score))];

console.log(`Escalate: ${escalate.noul.toFixed(2)}`);
console.log(
  `Owner:    ${owner} (model picked ${queue.choice}, confidence ${queue.confidence.toFixed(2)})`,
);
console.log(`Respond:  ${respondWithin}`);
```

```py title="Python"
import json
import os
import urllib.error
import urllib.request

base_url = "https://api.subq.ai/v1"

# The text to judge.
state = (
    "Patient with asthma reports a sore throat, fever since yesterday, and "
    "shortness of breath walking to the kitchen this morning."
)

# One question per judgment: a yes/no gate, an owning team, a response time.
questions = {
    "escalate": {
        "type": "noul",
        "instructions": (
            "Should a nurse see this chat before the patient books anything?"
        ),
        "criteria": {
            "true": (
                "Breathing trouble, chest pain, or a flare of a known condition"
            ),
            "false": "Stable symptoms the patient can book for themselves",
        },
    },
    "queue": {
        "type": "choice",
        "instructions": "Which team should own this chat?",
        "criteria": {
            "nurse_line": "Needs a nurse to assess symptoms today",
            "primary_care": "Book with the patient's own doctor",
            "pharmacy": "Refill or medication question only",
            "front_desk": None,
        },
    },
    "acuity": {
        "type": "score",
        "instructions": "How soon should someone respond?",
        "criteria": ["Within a week", "Within a day", "Within an hour"],
    },
}

request = urllib.request.Request(
    f"{base_url}/systemone",
    method="POST",
    headers={
        "Authorization": f"Bearer {os.environ['SUBQ_API_KEY']}",
        "Content-Type": "application/json",
    },
    data=json.dumps(
        {
            "model": "subq-snap-1.1",
            "state": state,
            "questions": questions,
        }
    ).encode(),
)

try:
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.load(response)
except urllib.error.HTTPError as error:
    detail = json.load(error)["detail"]
    raise RuntimeError(
        f"{error.code} {detail['error_type']}: {detail['message']}"
    ) from error

answers = result["answers"]
escalate = answers["escalate"]["noul"]
queue = answers["queue"]
acuity = answers["acuity"]

# Your code decides what happens next. Unsure routing goes to a nurse,
# and so does anything the gate says needs one.
owner = queue["choice"] if queue["confidence"] >= 0.6 else "nurse_line"
if escalate >= 0.5:
    owner = "nurse_line"

respond_within = acuity["legend"][str(round(acuity["score"]))]

print(f"Escalate: {escalate:.2f}")
print(
    f"Owner:    {owner} "
    f"(model picked {queue['choice']}, confidence {queue['confidence']:.2f})"
)
print(f"Respond:  {respond_within}")
```

### Building reliable decision workflows

Keep your code in charge. Rules you can write down belong in code. Ask the
model only for the judgment code can't make, then let code decide what happens
next.

- **One judgment per question.** Split a broad question into narrow ones, like
  the gate, owner, and deadline above. Code then combines the answers.
- **Ask related questions together.** Questions about the same `state` go in
  one request, so the state is sent once.
- **Send only what the decision needs.** Trim `state` to the relevant fields,
  and name the field an instruction is about.
- **Set thresholds from your own data.** Run the questions over cases you've
  already labeled and choose cutoffs from the results.
- **Send uncertain or high-impact cases to a person.** Outputs can vary between
  requests, so route low `confidence`, a noul near `0.5`, or a costly mistake
  to review.
- **Retry `429` and `5xx` with backoff.** Fix a `400` or `422` before resending;
  a retry won't change it.

## Request

The JSON body requires:

- `model` — a decision model ID, such as `subq-snap-1.1`. See
  [Models](/using-the-api/models/).
- `state` — the text, object, or array to evaluate. To ask about a document,
  send its text. See [Documents](#documents).
- `questions` — 1–128 named noul, choice, or score questions. Each uses
  `instructions` and type-specific `criteria`, which can contain strings,
  objects, or arrays. Answer keys match the question names, which can be up to
  100 characters.

The request must fit the model's 384K-token (393,216) context window. A request
over the limit, or close to it, fails with `400`.

Optional:

- `images` — up to 4 images to evaluate alongside `state`. See
  [Images](#images).

### Noul

A noul is a yes/no gate. Its answer is `noul`, the probability of yes from `0`
to `1`. Optional `criteria.true` and `criteria.false` describe both outcomes.

### Choice

A choice selects one named option. Define 2–255 options in `criteria`; each
option's description may be `null`. The answer includes `choice`, a probability
for every option, and `confidence`.

### Score

A score uses 2–10 ordered levels. The answer includes a probability-weighted
`score`, so it can fall between levels, plus `legend`, `probabilities`, and
`confidence`.

### Documents

Use a document to fact-check a claim against its source, find the passage that
backs an answer, or tag a record from its text.

The Decisions API takes no files. To ask about a PDF, Word file, or other
document, extract its text and send it as `state`, on its own or as a field
next to other data. Run OCR on scanned PDFs first.

- **Label the parts.** Mark pages, sections, or passages in the text, like
  `[P2]` or `--- page 24 ---`, so options can name them.
- **Ask where.** A choice whose options are those labels returns a probability
  for each location. Add an option like `not_found` for when the document
  doesn't say.

Send the text as a `state` field, and use the labels as `choice` options:

```bash title="cURL"
curl --request POST \
  --url https://api.subq.ai/v1/systemone \
  --header "Authorization: Bearer $SUBQ_API_KEY" \
  --header 'Content-Type: application/json' \
  --data @- <<'EOF'
{
  "model": "subq-snap-1.1",
  "state": {
    "claim": "Under Harlow v. Pemberton (2019), a landlord must return a tenant's security deposit within 14 days of move-out, no exceptions.",
    "source": "Harlow v. Pemberton, State Court of Appeals (2019)\n\n[P1] Tenant Dana Harlow moved out of a two-bedroom apartment on June 1. Landlord Owen Pemberton kept her $1,800 deposit for 30 days, then returned $600 with a note that the rest covered carpet damage.\n\n[P2] We hold that Section 12 of the Residential Tenancy Act requires a landlord to return the deposit within 14 days of move-out, unless within those same 14 days the landlord sends the tenant a written, itemized list of the damage it intends to deduct. A landlord who sends the list in time may keep the listed amounts while the dispute is resolved.\n\n[P3] Pemberton sent no itemized list within 14 days. He therefore owes Harlow the full deposit and, under Section 15, a penalty equal to the amount wrongly withheld.\n\n[P4] Harlow argues that Section 12 sets a 14-day deadline \"with no exceptions,\" and that any deduction needs a court order. We disagree. The Act plainly allows deductions that are itemized in time.\n\n[P5] Judge Alvarez, dissenting: I would allow the itemized-list route only for landlords who also photographed the unit at move-in. Without that record, the 14-day deadline should apply to the whole deposit.\n\n[P6] Headnote (written by the publisher, not part of the opinion): Landlords must return deposits within 14 days."
  },
  "questions": {
    "support": {
      "type": "score",
      "instructions": "How well does the source support the claim as written?",
      "criteria": [
        "Not supported",
        "Partly supported",
        "Fully supported"
      ]
    },
    "best_passage": {
      "type": "choice",
      "instructions": "Which source passage states the court's rule on the claim's subject?",
      "criteria": {
        "P1": null,
        "P2": null,
        "P3": null,
        "P4": null,
        "P5": null,
        "P6": null,
        "not_found": "No passage states it"
      }
    },
    "omits_condition": {
      "type": "noul",
      "instructions": "Does the claim leave out a condition or exception that the court's holding sets?"
    },
    "no_exceptions_source": {
      "type": "choice",
      "instructions": "Where in the source does the claim's \"no exceptions\" come from?",
      "criteria": {
        "majority": "The court's own holding or reasoning",
        "party_argument": "An argument the court describes and rejects",
        "dissent": "The dissenting judge",
        "headnote": "The publisher's headnote, which is not law",
        "not_found": "The source never says it"
      }
    }
  }
}
EOF
```

`best_passage` returns `"choice": "P2"` with a probability for every label,
including `not_found`.

### Images

Add images to judge photos or screenshots alongside the text, such as checking
that a listing's photos match its description, or that a screenshot shows a
step is done.

Send each image as an object:

```json
{
  "images": [
    { "mediaType": "image/jpeg", "base64": "/9j/4AAQSkZJRgABAQAA..." }
  ]
}
```

- `mediaType` — `image/png`, `image/jpeg`, or `image/webp`.
- `base64` — the file bytes as one line of base64. No URL and no `data:`
  prefix.
- Send up to 4 images. Each can be up to 4 MiB decoded, with an 8 MiB decoded
  total. The whole request body can be up to 13 MiB.
- Each image costs 66 to about 1,600 input tokens, set by resolution rather than
  file size. Downscale anything above about 1.6 megapixels to cut the cost.
  Image tokens count toward the context window.
- Video is not supported. Sample up to 4 frames and send them as images.

```ts title="TypeScript"
import { readFileSync } from "node:fs";

const baseURL = "https://api.subq.ai/v1";

// The ticket note. The photo carries the rest: which device, and what shape it is.
const state = "The number row stopped working.";

// Plain base64 of the file bytes. No data: URL prefix.
// PNG, JPEG, or WebP, at most 4 MiB decoded per image.
const photo = readFileSync("./keyboard.jpg").toString("base64");

// One question per judgment. Every question sees the note and every image.
const questions = {
  shows_keyboard: {
    type: "noul",
    instructions: "Does the photo show a keyboard?",
    criteria: {
      true: "A keyboard is the main object",
      false: "No keyboard is visible",
    },
  },
  layout: {
    type: "choice",
    instructions: "Which keyboard layout is in the photo?",
    criteria: {
      full_size: "Desktop keyboard with a numeric keypad",
      tenkeyless: "Desktop keyboard with no numeric keypad",
      laptop: "Built into a laptop",
      not_a_keyboard: null,
    },
  },
  wear: {
    type: "score",
    instructions: "How worn does the keyboard look?",
    criteria: ["Looks new", "Everyday wear", "Replace it"],
  },
};

const response = await fetch(`${baseURL}/systemone`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${process.env.SUBQ_API_KEY}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    model: "subq-snap-1.1",
    state,
    images: [{ mediaType: "image/jpeg", base64: photo }],
    questions,
  }),
});

if (!response.ok) {
  const error = await response.json();
  throw new Error(
    `${response.status} ${error.detail.error_type}: ${error.detail.message}`,
  );
}

const result = await response.json();
const { shows_keyboard, layout, wear } = result.answers;

// A photo that is not a keyboard, or an unsure layout, goes back to the employee.
if (
  shows_keyboard.noul < 0.5 ||
  layout.confidence < 0.6 ||
  layout.choice === "not_a_keyboard"
) {
  console.log("Ask for a clearer photo of the keyboard.");
} else {
  const condition = wear.legend[String(Math.round(wear.score))];
  console.log(`Keyboard: ${layout.choice} (${condition})`);
}
```

```py title="Python"
import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

base_url = "https://api.subq.ai/v1"

# The ticket note. The photo carries the rest: which device, and what shape it is.
state = "The number row stopped working."

# Plain base64 of the file bytes. No data: URL prefix.
# PNG, JPEG, or WebP, at most 4 MiB decoded per image.
photo = base64.b64encode(Path("./keyboard.jpg").read_bytes()).decode("ascii")

# One question per judgment. Every question sees the note and every image.
questions = {
    "shows_keyboard": {
        "type": "noul",
        "instructions": "Does the photo show a keyboard?",
        "criteria": {
            "true": "A keyboard is the main object",
            "false": "No keyboard is visible",
        },
    },
    "layout": {
        "type": "choice",
        "instructions": "Which keyboard layout is in the photo?",
        "criteria": {
            "full_size": "Desktop keyboard with a numeric keypad",
            "tenkeyless": "Desktop keyboard with no numeric keypad",
            "laptop": "Built into a laptop",
            "not_a_keyboard": None,
        },
    },
    "wear": {
        "type": "score",
        "instructions": "How worn does the keyboard look?",
        "criteria": ["Looks new", "Everyday wear", "Replace it"],
    },
}

request = urllib.request.Request(
    f"{base_url}/systemone",
    method="POST",
    headers={
        "Authorization": f"Bearer {os.environ['SUBQ_API_KEY']}",
        "Content-Type": "application/json",
    },
    data=json.dumps(
        {
            "model": "subq-snap-1.1",
            "state": state,
            "images": [{"mediaType": "image/jpeg", "base64": photo}],
            "questions": questions,
        }
    ).encode(),
)

try:
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.load(response)
except urllib.error.HTTPError as error:
    detail = json.load(error)["detail"]
    raise RuntimeError(
        f"{error.code} {detail['error_type']}: {detail['message']}"
    ) from error

answers = result["answers"]
shows_keyboard = answers["shows_keyboard"]["noul"]
layout = answers["layout"]
wear = answers["wear"]

# A photo that is not a keyboard, or an unsure layout, goes back to the employee.
if (
    shows_keyboard < 0.5
    or layout["confidence"] < 0.6
    or layout["choice"] == "not_a_keyboard"
):
    print("Ask for a clearer photo of the keyboard.")
else:
    condition = wear["legend"][str(round(wear["score"]))]
    print(f"Keyboard: {layout['choice']} ({condition})")
```

### cURL with an image

`openssl base64 -A` writes the file as one line. The heredoc is unquoted so the
shell encodes the file before the request is sent. Shrink the photo first so
the decoded file stays under 4 MiB.

```bash
curl -sS -X POST https://api.subq.ai/v1/systemone \
  -H "Authorization: Bearer $SUBQ_API_KEY" \
  -H "Content-Type: application/json" \
  --data-binary @- <<EOF
{"model":"subq-snap-1.1","state":"The number row stopped working.","images":[{"mediaType":"image/jpeg","base64":"$(openssl base64 -A -in keyboard.jpg)"}],"questions":{"shows_keyboard":{"type":"noul","instructions":"Does the photo show a keyboard?","criteria":{"true":"A keyboard is the main object","false":"No keyboard is visible"}},"layout":{"type":"choice","instructions":"Which keyboard layout is in the photo?","criteria":{"full_size":"Desktop keyboard with a numeric keypad","tenkeyless":"Desktop keyboard with no numeric keypad","laptop":"Built into a laptop","not_a_keyboard":null}},"wear":{"type":"score","instructions":"How worn does the keyboard look?","criteria":["Looks new","Everyday wear","Replace it"]}}}
EOF
```

An invalid image fails with `422` `validation_error`. A file over 4 MiB:

```json
{
  "detail": {
    "error_type": "validation_error",
    "message": "images/0: image over 4 MiB"
  }
}
```

Bytes that do not match `mediaType` fail the same way:
`images/0: image bytes must match the PNG, JPEG, or WebP mediaType.` The same
status covers a URL or `data:` prefix, a bad decode, more than 4 images, or more
than 8 MiB decoded in total.

## Response

```json
{
  "model": "subq-snap-1.1",
  "answers": {
    "escalate": {
      "type": "noul",
      "noul": 0.92
    },
    "queue": {
      "type": "choice",
      "choice": "nurse_line",
      "probabilities": {
        "nurse_line": 1,
        "primary_care": 0,
        "pharmacy": 0,
        "front_desk": 0
      },
      "confidence": 1
    },
    "acuity": {
      "type": "score",
      "score": 1.86,
      "legend": {
        "0": "Within a week",
        "1": "Within a day",
        "2": "Within an hour"
      },
      "probabilities": {
        "0": 0,
        "1": 0.13,
        "2": 0.87
      },
      "confidence": 0.79
    }
  },
  "usage": {
    "input_tokens": 477,
    "output_tokens": 0
  }
}
```

You pay only for input tokens; `output_tokens` is always `0`.

Stored decisions, including images, follow the
[data-retention policy](/using-the-api/data-retention/).

## Errors

Errors use a `detail` object:

```json
{
  "detail": {
    "error_type": "validation_error",
    "message": "questions/queue: must have required property 'criteria'"
  }
}
```

- `400` — input over the token limit, or a request the model rejects.
- `401` — missing or invalid credentials.
- `402` — insufficient credits.
- `403` — the API key cannot use the requested model.
- `422` — invalid request (including an invalid or oversized image) or a model
  that is not a decision model.
- `429` — rate limit exceeded.
- `5xx` — server error. `503` means the service is temporarily unavailable.
