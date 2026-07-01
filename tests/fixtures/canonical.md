# Capsule

## Objective
Add Google OAuth

## Current Understanding
- auth uses JWT sessions

## Constraints
- email/password login must keep working

## Invariants
- session model unchanged

## Acceptance
- user can sign in with Google

## Decisions
- Use OAuth2 authorization-code flow
  - rationale: server-side secret; no token in browser
  - evidence: file:auth/google.py, commit:a1b2c3d (verified: false)

## Open Questions
_None._

## Open Tasks
_None._

## Resolved Questions
- (q1) Enterprise SSO in scope? -> No — defer. (resolved_by r1)

## Progress
- frontend button wired
  - evidence: commit:7d4e9f0 (verified: false)
