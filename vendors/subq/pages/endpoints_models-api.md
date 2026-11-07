---
title: Models API
description: List the model IDs available to your API key.
---

Use the Models API to list the model IDs available to your API key.

## List models

```
GET /v1/models
```

### Request

```bash title="cURL"
curl --request GET \
  --url https://api.subq.ai/v1/models \
  --header "Authorization: Bearer $SUBQ_API_KEY"
```

```ts title="TypeScript"
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.SUBQ_API_KEY,
  baseURL: "https://api.subq.ai/v1",
});

const models = await client.models.list();
console.log(models.data.map((model) => model.id));
```

```py title="Python"
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["SUBQ_API_KEY"],
    base_url="https://api.subq.ai/v1",
)

models = client.models.list()
print([model.id for model in models.data])
```

### Response

The response follows the OpenAI-compatible list shape. Use a returned `id` with
the endpoint that supports that model.

```json
{
  "object": "list",
  "data": [
    {
      "id": "subq-preview",
      "name": "SubQ Preview",
      "object": "model",
      "created": 0,
      "owned_by": "subquadratic"
    },
    {
      "id": "subq-snap-1.1",
      "name": "SubQ Snap 1.1",
      "object": "model",
      "created": 0,
      "owned_by": "subquadratic"
    }
  ]
}
```

For each model's endpoints, inputs, and pricing, see [Models](/using-the-api/models/).
