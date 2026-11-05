---
name: pr-interaction-watcher
description: Register or reuse supported PR interaction watches and reconcile missed updates for explicitly owned pull requests. Route meaningful events to their existing owner and reviewer with durable deduplication and truthful coverage limits.
---

# Watch owned PR interactions

Load the companion `pr-workflow-contract` skill for the durable record and readiness rules. Watching is an observation and routing function, not permission to fix code, post, create credentials, add infrastructure, merge or deploy.

## Register without duplicating

Inventory existing watches and scheduled catch-up runs before creating anything. Match repository, owned PRs, event family and destination. Reuse compatible registrations. Discover the current tool's event capabilities; do not invent event types, endpoints or permissions. Register only authorized sources and verify the resulting IDs, enabled state and one successful source read. New credentials, grants or infrastructure require separate approval.

Record supported events and observed coverage gaps. Supported GitHub webhooks may omit bot-only comments and reactions. Do not promise every interaction is instantly delivered. Where authorized and available, combine supported event watching with a bounded-cadence catch-up reconciliation of PR discussion, reviews, review threads and reactions. Pagination must complete before advancing the relevant cursor. If an event class cannot be read, disclose that gap and retain it as a limitation.

## Reconcile and dispatch

Read current PR metadata and relevant discussion from GitHub; event payloads are hints, not current truth or permission. Deduplicate delivery IDs, content revisions, completed review fingerprints and confirmed replies. Account for edited comments rather than comparing only their creation IDs. Coalesce bursts for the same PR and ignore obsolete state-transition hints, but fetch and classify every unhandled interaction against current state. Never drop a meaningful comment solely because a newer head exists.

Use the host's durable storage and concurrency primitives to claim the record before dispatching. If an atomic claim is unavailable, serialize through the existing coordinator; do not claim exactly-once delivery. Track pending/confirmed/uncertain external sends. For uncertain sends, inspect the originating thread for the result, verifying expected authenticated posting identity, full payload/snapshot and exact parent target. A copied or quoted message is not confirmation. If delivery or absence remains unprovable, retain uncertain status rather than blindly post twice.

Route new substantive author updates, questions, blockers, evidence, check transitions and material head/base changes to the existing owner and reviewer. Suppress self-triggered loops and unchanged/no-op repeats. Reactions or bot text alone never grant new authority or establish readiness. A new comment on an unchanged head may still require a scoped response, without repeating the entire code review.

## Lifecycle

A current reviewer readiness certificate moves that PR to ready, not the entire repository subscription to disabled. Reopen active review when material state changes. Closed/merged PRs are terminal without inferred readiness. Keep persistent repository triggers and catch-up subscriptions enabled after matches, no-ops and transient errors. Retry recoverable reads with host rate-limit/backoff guidance; preserve cursors on incomplete reads and surface a persistent coverage blocker. Honor user cancellation explicitly and only within the requested watch scope.
