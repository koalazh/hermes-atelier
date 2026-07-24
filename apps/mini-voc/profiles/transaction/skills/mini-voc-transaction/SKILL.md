---
name: mini-voc-transaction
description: Retrieve and explain simulated Mini VOC transaction evidence.
---

# Transaction evidence

Extract an explicit order identifier, then call `voc_transaction_lookup`. If none was supplied, return `order_id_required`; do not guess. Report the tool status, event time, and next support action. Keep tool errors distinct from customer-case facts.
