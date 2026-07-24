# ADR 004: Atelier Run is not a Hermes Session

Status: Accepted

Each Profile keeps its own Hermes transcript Session and execution Run. An Atelier Run only correlates them. Transcript Session IDs are run-specific; stable Memory keys are separate. Atelier never copies Sessions into its authoritative store.
