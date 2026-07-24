# ADR 005: Human-approved improvement

Status: Accepted

Reviewer is read-only and evidence-bounded. Builder emits a candidate Patch. The backend validates and dry-runs it, but only explicit approval applies it. The unchanged scenario is replayed, and the user may keep or revert. No component can declare self-improvement from one unverified output.
