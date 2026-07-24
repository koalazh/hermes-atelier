# Hermes Atelier V1

## Intent

Hermes Atelier gives a developer one restrained space to turn business intent into complete Hermes Agents, observe real cross-Profile collaboration, diagnose it from evidence, and apply a reviewable change only after explicit approval.

It is an Atelier rather than an AgentHub because it does not own a general registry, scheduler, remote mesh, tenant model, or production control plane. An application remains a group of native Hermes Profile Distributions in this repository. Hermes remains the execution environment.

## Why these boundaries

Builder is a Skill-driven Hermes Profile because intent alignment, boundary discovery, and Profile design require Agent judgment. A Python template would silently become a role catalogue and workflow generator. Builder defaults to one Profile and records the concrete isolation reason for every split.

A unified Web UI is still necessary: the development loop needs one place to approve drafts, see true parent/child Runs, compare trace evidence, inspect a candidate Diff, and replay the same scenario. The Atelier tab adds only those operations. Hermes Dashboard continues to own Profile management, Config, keys, Skills, MCP, Sessions, Chat, logs, and Gateway management.

Only `atelier_call` crosses Profiles because arbitrary curl calls cannot establish trustworthy caller identity or parent/child Session and Run links. The tool validates the application allowlist and records the call boundary; the calling Agent still decides whether to call, which expert to use, ordering, sufficiency, aggregation, and degradation.

Hermes Self-Evolution and Atelier Review are separate. Reviewer reads a frozen, scoped evidence bundle and cannot modify an application, Memory, scenarios, its own rubric, or formal Profiles. Builder may produce a path-restricted candidate Patch. Only a backend approval state can apply it, and validation requires replay.

## Stable boundary and Agent autonomy

Atelier controls Profile identity, app membership, call allowlists, loopback endpoints, runtime credentials, Session/Run correlation, trace capture, file scope, explicit approvals, process health, and failure states. Agents control business interpretation, investigation, delegation, tools, evidence sufficiency, and output.

Targets, aligned goals, Profile boundaries, acceptance scenarios, versions, traces, reviews, and proposals may be externalized. Business steps, routing predicates, fan-out, aggregation, judging, and retries may not be encoded in Atelier core or `app.yaml`.

## Non-goals

V1 has no multiplex Gateway, workflow DSL/editor, generic Agent Registry or mesh, async task platform, auto-evolution, auto-release, multi-tenancy, RBAC, production tracing, custom Memory/Session/Runtime/model router, business UI, marketplace, or Hermes core patch.

## Deletion strategy

If Hermes supplies a reliable native equivalent, delete the Atelier seam. Do not retain duplicate abstractions for compatibility. Application assets can survive even if the workbench contracts.

## Kill or pivot

Stop expansion when Hermes natively provides cross-Profile calls and trace, app grouping and Review, or makes `atelier_call` redundant; when a third application requires a core business special case; when Builder output needs sustained large rewrites; when Reviewer suggestions do not survive repeat scenarios; when developers prefer direct Dashboard/Profile use; or when maintenance exceeds debugging value.

The preferred pivots are, in order: delete duplicate modules, shrink to one Hermes Plugin, shrink to the Builder Skill, contribute generic capabilities upstream, and keep useful business applications.
