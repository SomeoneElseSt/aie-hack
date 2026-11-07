---
title: Data retention
description: How long SubQ stores prompts, completions, and conversation history.
---

Inputs and outputs from [Chat Completions](/endpoints/chat-completions-api/)
and [Decisions](/endpoints/decisions-api/) requests are deleted within 60 days
of processing. Organizations on [zero data retention](#zero-data-retention)
store nothing.

Other data has no expiry:

- **Conversation history.** Saved [Responses](/endpoints/responses-api/) turns
  stay stored. Each belongs to the conversation named in the response's
  `conversation.id`;
  [delete that conversation](/endpoints/conversations-api/#delete-a-conversation)
  to remove it with every turn in it.
- **Inline PDFs.** A PDF sent as `file_data` on Chat Completions is stored, and
  the API can't delete it. With `store: false`, SubQ deletes it once the
  request is processed. Or [upload the file](/endpoints/files-api/) and delete
  it when you're done.
- **Uploaded files.** Files sent to the [Files API](/endpoints/files-api/) stay
  until you [delete them](/endpoints/files-api/#delete-file).

To keep a turn or request out of storage, see
[Opting out per request](#opting-out-per-request).

Content flagged for a potential violation of the Terms or Usage Policy may be
kept while SubQ investigates the violation. SubQ may also keep inputs and
outputs longer when the law requires it.

SubQ always records model, token counts, timing, and your
[`metadata`](/endpoints/chat-completions-api/#metadata) tags for billing and
support. That record never includes prompts or completions.

## Zero data retention

Requests work as usual, but nothing is stored afterward. To enable it for your
organization, [submit a ZDR request](https://share-na2.hsforms.com/1ikOZ84D1RACcMJlibb1z9w418zam).

| Endpoint                                             | Behavior                                                                                                            |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| [Chat Completions](/endpoints/chat-completions-api/) | Works as usual. Nothing is stored.                                                                                  |
| [Responses](/endpoints/responses-api/)               | Works, but turns aren't saved. Send the full context in `input` on every request instead of `previous_response_id`. |
| [Conversations](/endpoints/conversations-api/)       | Unavailable (`403` `zero_data_retention`).                                                                          |
| [Decisions](/endpoints/decisions-api/)               | Works as usual. Nothing is stored.                                                                                  |
| Inline PDFs (`file_data`)                            | Rejected (`400` `document_source_unsupported`). Upload the file and pass [`file_id`](/using-the-api/file-inputs/).  |

## Opting out per request

To keep a single request out of storage, send `store: false` on
[Chat Completions](/endpoints/chat-completions-api/#storage) or
[Responses](/endpoints/responses-api/#storage).
