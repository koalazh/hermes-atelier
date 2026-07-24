# ADR 006: Project-local Hermes home

Status: Accepted

All subprocesses receive the absolute `<repo>/.hermes-runtime` as `HERMES_HOME` plus explicit `-p <profile>`. Distribution source remains in Git; runtime Memory, Sessions, credentials, logs, and state do not. Removing the repository removes the complete development environment, but this boundary is not an OS sandbox.
