# Design decisions

## 1. Metadata before model inference

A detector and the event service are separate concerns. A small typed event contract allows deterministic testing without downloads, GPUs, credentials, or uncertain detector accuracy. This project implements the event service; the simulator is explicitly synthetic.

## 2. Synchronous request/transaction pipeline

Each accepted request is durable before receiving 201. No process-local queue can lose acknowledged work on restart. This trades throughput for simple correctness; a broker would require its own delivery and deduplication design.

## 3. SQLite with explicit writer serialization

The check for an existing ID and insertion must not race. BEGIN IMMEDIATE covers that whole decision. A unique key alone could detect a collision, but the explicit transaction also makes payload conflict handling and audit insertion straightforward. Transactions are short; bounded lock waiting can still fail under sustained contention.

## 4. Shared key and local access

Authentication is intentionally basic, fail-closed when unset, and checked with constant-time comparison. The dashboard stores the key in page memory only. This does not provide user identity or production authorization. Compose binds to loopback; use a proper identity layer and TLS gateway for any broader deployment.

## 5. Explicit timestamps

Inputs require a timezone. occurred_at comes from the producer and received_at from the server; sorting uses received_at so producer clock skew does not reorder server receipt history. The prototype does not reject future producer timestamps or claim clock synchronization.

## 6. Minimal audit

Ingestion and acknowledgement write audit entries in the same SQLite transaction as their state changes. No operator identity is captured because authentication uses one shared key. The table is not an immutable compliance log.
