---
title: Quickstart
description: Send your first SubQ Decisions API request.
---

> Status: Public preview

Make your first API request in minutes.

**Decision Models (Public Preview):** [`subq-snap-1.1`](/using-the-api/models/#subq-snap-11) is available to all accounts for returning decision outputs.

**Text generation models (Early Access):** [`subq-preview`](/using-the-api/models/#subq-preview) generates text but requires organization enablement. [Join the waitlist](https://subq.ai/small#waitlist).

## 1. Get your API key

Sign up at [console.subq.ai](https://console.subq.ai) and create an API key from
the dashboard. Store it in an environment variable:

```bash
export SUBQ_API_KEY="sk-your-api-key"
```

## 2. Check account access

Make sure your account has credits before sending requests. A request without
available credits returns `402`.

## 3. Send a request

```bash title="cURL"
curl --request POST \
  --url https://api.subq.ai/v1/systemone \
  --header "Authorization: Bearer $SUBQ_API_KEY" \
  --header 'Content-Type: application/json' \
  --data '
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
    }
  }
}
'
```

```ts title="TypeScript"
const baseURL = "https://api.subq.ai/v1";

const response = await fetch(`${baseURL}/systemone`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${process.env.SUBQ_API_KEY}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    model: "subq-snap-1.1",
    state:
      "Patient with asthma reports a sore throat, fever since yesterday, and shortness of breath walking to the kitchen this morning.",
    questions: {
      escalate: {
        type: "noul",
        instructions: "Should a nurse see this chat before the patient books anything?",
        criteria: {
          true: "Breathing trouble, chest pain, or a flare of a known condition",
          false: "Stable symptoms the patient can book for themselves",
        },
      },
    },
  }),
});

if (!response.ok) {
  const error = await response.json();
  throw new Error(
    `${response.status} ${error.detail.error_type}: ${error.detail.message}`,
  );
}

const result = await response.json();
console.log(`Escalate: ${result.answers.escalate.noul.toFixed(2)}`);
```

```py title="Python"
import json
import os
import urllib.error
import urllib.request

base_url = "https://api.subq.ai/v1"

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
            "state": (
                "Patient with asthma reports a sore throat, fever since "
                "yesterday, and shortness of breath walking to the kitchen "
                "this morning."
            ),
            "questions": {
                "escalate": {
                    "type": "noul",
                    "instructions": (
                        "Should a nurse see this chat before the patient "
                        "books anything?"
                    ),
                    "criteria": {
                        "true": (
                            "Breathing trouble, chest pain, or a flare of a "
                            "known condition"
                        ),
                        "false": (
                            "Stable symptoms the patient can book for "
                            "themselves"
                        ),
                    },
                },
            },
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

print(f"Escalate: {result['answers']['escalate']['noul']:.2f}")
```

The answer is in `answers.escalate.noul`, the probability of yes from `0` to
`1`. See the [Decisions API](/endpoints/decisions-api/) for choice and score
questions, images, and errors.
