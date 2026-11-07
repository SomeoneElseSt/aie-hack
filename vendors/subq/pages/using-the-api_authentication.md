---
title: Authentication
description: Authenticate SubQ API requests with bearer tokens.
---

Every API request requires an API key in the `Authorization` header using the
Bearer scheme.

## Create an API key

Generate a key from [console.subq.ai](https://console.subq.ai), store it outside
your source tree, and send it with each request. Listing
[models](/endpoints/models-api/) is a quick way to check a key:

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

## Use environment variables

Set the key in your local shell or deployment environment:

```bash
export SUBQ_API_KEY="sk-your-api-key"
```

Then read `SUBQ_API_KEY` from your application configuration and pass it to your
HTTP client or OpenAI SDK.

## Key security

- **Store securely.** Keys are shown once at creation and cannot be retrieved later.
- **Rotate regularly.** Create new keys and revoke old ones from the console.
- **Never commit to source control.** Use environment variables or a secrets manager.
