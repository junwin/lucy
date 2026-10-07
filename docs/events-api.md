# Episodic events API

These routes supplement `/chats`; existing chat routes remain available.
Use the configured API key in `X-API-Key` or `Authorization: Bearer`.
Both operations require `accountName` and `sessionId` query parameters.
A missing session or wrong account returns 404 without exposing its contents.

## Last N active events

```sh
curl -H "X-API-Key: $LUCY_API_KEY" \
  "$LUCY_URL/events?accountName=alice&sessionId=SESSION_ID&count=10"
```

`count` defaults to 10 and accepts integers from 0 to 1000. Zero returns an empty
list. Events are selected from the end of active history and returned in stored
sequence order (oldest to newest within the selected tail). Invalidation
markers and inactive events are excluded by galet-memory.

The response contains `account_name`, `session_id`, `count`, `last_event_id`,
and `events`. Each event includes `event_id`, `session_id`, `sequence`, `role`,
`actor`, `kind`, `content`, `metadata`, `correlation_ids`, `created_at`, and
`stored_at`. Full content keeps its original JSON type; timestamps are ISO 8601.
`last_event_id` is the store's append tail and may identify a control marker,
rather than the last returned visible event.

## Deactivate an exchange

```sh
curl -X DELETE -H "X-API-Key: $LUCY_API_KEY" \
  "$LUCY_URL/events/CORRELATION_ID?accountName=alice&sessionId=SESSION_ID"
```

This calls galet-memory's `invalidate_exchange`. It deactivates all events
linked to that exact correlation within the account/session, including the
user message, responses, and any other linked activity. It does not expand the
operation to a broader trace. Galet-memory retains originals, appends an
invalidation marker, and invalidates affected derived digests according to its
provenance policy. Future active reads and prompt history exclude invalidated
content. `/chats/<session_id>` also uses active history, so reload preserves the
result. An append using the invalidated correlation is rejected by the store.

The response contains `ok`, `account_name`, `session_id`, `correlation_id`,
`status`, `event_count`, `event_ids`, `invalidated_digest_ids`, `marker_event_id`,
and `unprovenanced_digests_invalidated`. A successful deactivation or repeat
returns 200 (`invalidated` or `already_invalidated`); an unknown correlation
returns 404 (`not_found`). Invalid input returns 400; a concurrency conflict
returns 409. There is no restoration route.

## Remaining issue #242 work

This is the endpoint portion of Lucy #242. The gptChum deletion action and
Lucy-side running-exchange exclusion still need implementation. The endpoint
currently permits invalidation of a running correlation; the store then rejects
later appends for it. It is suitable for testing completed exchanges, but that
storage behavior does not fulfill the issue's running-exchange restriction.
