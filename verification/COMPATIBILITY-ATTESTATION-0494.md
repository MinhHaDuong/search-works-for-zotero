# Compatibility-attestation aggregation — ticket 0494

Date: 2026-09-03

## Question

Is an opt-in aggregation endpoint justified after local embedder validation is
available?

## Finding

No endpoint is justified at this stage. The local result is authoritative for
the installation that creates or queries vectors. Aggregate counts have no
current consumer and are supporting evidence rather than a gate for ticket
0495.

An endpoint would additionally require decisions that the project has not
made: an operator and destination, retention and deletion, treatment of IP
addresses and transport logs, abuse resistance, deduplication, rare-bucket
privacy, and the presentation policy for small samples. A client-only POST
would therefore create data custody without completing a useful aggregate.

## Consequence

Ticket 0494 closes without implementation under the author's 2026-09-03
ruling in `DECISIONS.md`. R31's optional `MAY` remains unchanged, so a later
ticket can revisit aggregation after its operator, consumer, and privacy
design are explicitly authorised.
