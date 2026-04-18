# Tree Analysis

## Goal

Turn a repository into a hierarchy of ownership scopes that can each receive concise agent instructions.

## Scope Heuristics

Use these signals to decide whether a folder deserves its own nested instruction file:

- command differences: separate setup, build, test, or generation steps
- ownership differences: different runtime, package, service, or domain
- policy differences: special security, data, or review rules
- dependency differences: a folder depends on a different subsystem
- churn differences: a subtree changes often and needs local guidance
- documentation differences: a folder needs a distinct instruction surface because the parent would become too broad

Do not create a new level just because the path is deep. Create a new level when behavior changes.
Do not create nested files for every directory if a single doc can clearly describe the whole scope.

## Agent Roles

Use one subagent per independent scope:

- `tree scout`: summarize top-level folders and identify ownership candidates
- `domain scout`: analyze one domain or package boundary
- `shared-systems scout`: inspect shared libraries, utilities, and cross-cutting modules
- `instruction drafter`: draft or update the actual docs
- `verifier`: compare docs to the real tree and list omissions

## Suggested Agent Output

Ask each agent to return:

1. owned paths
2. purpose of the scope
3. commands used inside the scope
4. local conventions or constraints
5. inbound and outbound dependencies
6. candidate doc file path
7. uncertainty list
8. whether another nested file is actually warranted

## Stop Conditions

Stop dividing the tree when:

- the next level would only repeat the same commands or rules
- the subtree is generated or vendor-owned
- the subtree has no local conventions beyond the parent
- the subtree is too small to justify separate guidance
- no command, policy, or dependency boundary changes below that point

## What To Ignore

Exclude or de-prioritize:

- vendored dependencies
- generated code
- build artifacts
- cache directories
- lockfiles unless they define real workflow constraints
- third-party assets unless the repo owns them
- opaque binary blobs unless they are first-class repo assets
