# ADR 003: One observable call boundary

Status: Accepted

All observed cross-Profile calls use `atelier_call`. One seam is sufficient to validate caller identity and allowlists and to associate real parent/child Sessions and Runs. The tool never selects, orders, retries, aggregates, or interprets experts.
