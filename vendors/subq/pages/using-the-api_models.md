---
title: Models
description: Supported SubQ model IDs and what each one accepts.
---

Pass the model ID in the `model` field. IDs are case-sensitive. To list the IDs
available to your API key, use the [Models API](/endpoints/models-api/).

## SubQ Snap 1.1

The default Decision model for fast, structured decisions.

- Model ID: `subq-snap-1.1`
- Status: Public preview
- Endpoint: [Decisions](/endpoints/decisions-api/)
- Modalities: Text (input and output), Image (input only)
- Features: [Images](/endpoints/decisions-api/#images)
- Pricing: Input ($0.04 / 1M tokens), Output (Free)

## SubQ Preview

Use this model for long-context chat.

`subq-preview` is in early access and is enabled per organization. Until it is
enabled for yours, requests return `403` `model_not_allowed`, even with a valid
API key. To check, call the
[Models API](/endpoints/models-api/) with your API key: it lists only the
models that key can call. [Request access](https://subq.ai/small#waitlist).

- Model ID: `subq-preview`
- Status: Early access
- Endpoint: [Chat Completions](/endpoints/chat-completions-api/), [Responses](/endpoints/responses-api/)
- Modalities: Text (input and output), Image (input only)
- Features: [Files](/using-the-api/file-inputs/), [Function calling](/using-the-api/function-calling/)
