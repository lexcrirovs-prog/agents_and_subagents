---
type: shared-team
updated: 2026-04-29
---

# HandoffPlaybook

## Purpose

- let departments resolve cross-lane questions before reporting to the director
- keep one accountable owner for every task
- prevent the user from receiving unresolved internal back-and-forth

## Internal Resolution Rule

When a sub-agent has a question that another department can answer:

1. Ask the relevant peer through `tools/agent_tools/ask_agent.py` or `ask_agent_async.py`.
2. Include the minimum handoff packet below.
3. Read the peer answer and decide how it changes the work.
4. Return one synthesized answer to the caller.
5. Escalate to `main` only when a business decision, external approval, missing credential, or unresolved conflict remains.

## Minimum Handoff Packet

Every peer request should include:

1. Context
2. Exact ask
3. Expected deliverable
4. Time horizon or urgency
5. Constraint, risk, or source boundary

## Peer Return Shape

The helping agent should answer in this order:

1. `ACCEPTED` or `BLOCKED`
2. Direct answer
3. Evidence or source used
4. Risk or caveat
5. Next move if needed

## Director Return Shape

When reporting back to `main`, the owning agent should answer in this order:

1. `DONE`, `PARTIAL`, or `BLOCKED`
2. Final synthesized answer
3. Peer departments consulted
4. Remaining risk
5. Recommended next action

## Escalation Ladder

### Level 0 - Stay In Lane

- the task is inside your own competence
- no peer help is needed

### Level 1 - Bounded Peer Consult

- you need one department slice from a peer
- ownership stays with you

### Level 2 - Multi-Department Resolution

- two or more departments must contribute
- the owner coordinates internally and sends one resolved answer upward

### Level 3 - Director Escalation

- ownership is unclear
- department views conflict materially
- external approval, credentials, money, legal sign-off, or publication authority is required
