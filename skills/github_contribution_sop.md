# GitHub Contribution SOP
**Trigger**: opening a PR against an open-source project (bug fix / feature / docs).
**Disabled when**: only reading code, no submission needed.
**Core principle**: one PR does one thing, push only after tests pass, respect the project's conventions.

## Pre-flight (first time on each new project)
1. **Read the project conventions** (mandatory, do not skip)
   ```
   file_read('CONTRIBUTING.md')               # contribution guide
   file_read('.github/PULL_REQUEST_TEMPLATE.md')  # PR template
   file_read('.github/ISSUE_TEMPLATE/')        # Issue templates
   ```
   If those are missing, read the Contributing section in the README. If even that is missing, follow this SOP's defaults.

2. **Understand the project structure and how to test**
   ```
   # Find the test command
   file_read('package.json')   # Node: scripts.test
   file_read('Makefile')       # or Makefile
   file_read('pyproject.toml') # Python: [tool.pytest] etc.
   ```
   Note the test command. A PR you cannot run tests on is an unverified PR.

3. **Fork + Clone**
   ```
   code_run('bash', 'gh repo fork OWNER/REPO --clone && cd REPO && git remote -v')
   ```

## Workflow (per PR)

### Step 1: Confirm the goal
- Read the related Issue (if any).
- Write one sentence: what you are changing and why.
- Check whether someone is already working on it (Issue assignee, recent PRs).

### Step 2: Create a branch
```
code_run('bash', 'git checkout -b fix/issue-description && git status')
```
Branch naming: `fix/xxx` (bug fix), `feat/xxx` (feature), `docs/xxx` (docs).

### Step 3: Make the change
- **Minimize the diff**: only change what needs to change; do not refactor unrelated code.
- **Match the project style**: indentation, naming and comment style follow existing code.
- **Commit each logical step**:
  ```
  code_run('bash', 'git add -A && git commit -m "fix: short description"')
  ```
- Commit message format: follow project conventions (Conventional Commits or whatever the project uses).
  - If there is no convention, use: `type: short description`.
  - type: fix / feat / docs / refactor / test / chore.

### Step 4: Test (do not skip)
```
code_run('bash', 'project test command')   # npm test / pytest / go test ./...
```
**Checklist**:
- [ ] All existing tests pass?
- [ ] New behavior has matching tests? (if the project tests things)
- [ ] lint / type check pass? (if the project has them)

**Do not push if tests fail. Fix them first.**

### Step 5: Push + open the PR
```
code_run('bash', 'git push origin HEAD')
```
PR contents:
- **Title**: `type: short description` or follow the project template.
- **Body** must include:
  - What you changed (What).
  - Why you changed it (Why) — link to the issue with `Fixes #123`.
  - How you tested it (Testing).
- **Do not include**: over-explanation, unrelated context, self-promotion.

### Step 6: CI checks
After opening the PR wait for CI:
- All green -> wait for review.
- Failures -> read the logs, fix your issues.
  - If the failure is upstream / unrelated to your change, explain that in the PR.
  ```
  code_run('bash', 'gh run view --log-failed')
  ```

### Step 7: Respond to review
- **If a reviewer asks for a change, make it**, do not argue style preferences.
- **For technical disagreements**: politely explain your reasoning, but defer to the maintainer.
- **After fixes**: append a commit + tests + push. Do not force-push (unless the maintainer asks for a squash).
- **If a reviewer asks for tests** -> add them, this is not optional.

## Common mistakes (avoid)

| Mistake | Correct approach |
|---------|------------------|
| One PR doing many things | Split into independent PRs |
| Open the PR and forget about it | Check review status daily |
| Push without running tests | Step 4 is a hard gate |
| Inconsistent code style | Match existing code |
| Commit message says "update" | Say what actually changed |
| Force-push that erases review history | Append a commit |
| Empty PR description | Write What/Why/Testing |

## Follow-up state machine

```
PR submitted -> wait for CI
  CI green -> wait for review
    Review approved -> wait for merge
    Review requests changes -> fix + tests -> back to wait for CI
  CI red -> fix -> back to wait for CI
```

Each follow-up uses:
```
code_run('bash', 'gh pr status')
code_run('bash', 'gh pr checks PR_NUMBER')
code_run('bash', 'gh pr view PR_NUMBER --comments')
```
