# Git Quick Reference

> Fast-recall cheatsheet for Senior SDET / Automation Architects  
> Covers daily workflow, branching, rebasing, stashing, troubleshooting, and CI patterns

---

## Table of Contents
- [Config](#config)
- [Daily Workflow](#daily-workflow)
- [Branching](#branching)
- [Staging & Committing](#staging--committing)
- [Undoing Things](#undoing-things)
- [Stashing](#stashing)
- [Merging vs Rebasing](#merging-vs-rebasing)
- [Cherry-pick](#cherry-pick)
- [Remote Operations](#remote-operations)
- [Tagging](#tagging)
- [Log & Diff](#log--diff)
- [Bisect](#bisect)
- [Submodules](#submodules)
- [Aliases](#aliases)
- [Gotchas](#gotchas)
- [Quick Reference Card](#quick-reference-card)

---

## Config

```bash
# Identity (required first-time setup)
git config --global user.name  "Neil Marshall"
git config --global user.email "neil@example.com"

# Default branch name
git config --global init.defaultBranch main

# Preferred editor
git config --global core.editor "code --wait"     # VS Code
git config --global core.editor "vim"

# Diff / merge tool
git config --global merge.tool vscode

# Useful globals
git config --global pull.rebase true              # rebase on pull (recommended)
git config --global rebase.autoStash true         # auto-stash dirty working tree
git config --global core.autocrlf input           # LF on commit (Mac/Linux)

# View all config
git config --list --show-origin
```

---

## Daily Workflow

```bash
# Start of day — sync with remote
git fetch origin
git status

# Pull latest (rebase keeps history clean)
git pull --rebase origin main

# Create feature branch
git checkout -b feature/my-feature

# ... make changes ...

# Stage, commit, push
git add .
git commit -m "feat: add patient search endpoint test"
git push -u origin feature/my-feature

# Open PR, merge, then clean up
git checkout main
git pull --rebase origin main
git branch -d feature/my-feature
```

---

## Branching

```bash
# Create and switch
git checkout -b feature/my-feature               # classic
git switch -c feature/my-feature                 # modern (Git 2.23+)

# Switch to existing branch
git checkout main
git switch main

# List branches
git branch                                        # local
git branch -r                                     # remote
git branch -a                                     # all

# Rename branch
git branch -m old-name new-name

# Delete branch
git branch -d feature/done                        # safe (merged only)
git branch -D feature/nope                        # force delete

# Delete remote branch
git push origin --delete feature/done

# Track a remote branch
git checkout --track origin/feature/remote-branch

# See branch's upstream
git branch -vv
```

---

## Staging & Committing

```bash
# Stage
git add .                                         # all changes
git add src/tests/                                # directory
git add -p                                        # interactive hunk-by-hunk

# Unstage (keep changes in working tree)
git restore --staged <file>
git reset HEAD <file>                             # older syntax

# Commit
git commit -m "feat: add FHIR patient test"
git commit -am "fix: update selector"             # stage tracked files + commit

# Amend last commit (before push only)
git commit --amend -m "fix: corrected commit message"
git commit --amend --no-edit                      # amend without changing message

# Empty commit (useful for triggering CI)
git commit --allow-empty -m "ci: trigger pipeline"

# Commit message conventions (Conventional Commits)
# feat:     new feature
# fix:      bug fix
# docs:     documentation only
# test:     adding/updating tests
# refactor: code change, no feature/fix
# chore:    build process, tooling
# ci:       CI/CD changes
```

---

## Undoing Things

```bash
# Discard working tree changes (DESTRUCTIVE)
git restore <file>
git checkout -- <file>                            # older syntax
git restore .                                     # discard all

# Undo last commit — keep changes staged
git reset --soft HEAD~1

# Undo last commit — keep changes unstaged
git reset --mixed HEAD~1                          # default

# Undo last commit — discard changes (DESTRUCTIVE)
git reset --hard HEAD~1

# Revert a pushed commit (safe — creates new commit)
git revert <commit-hash>
git revert HEAD                                   # revert last commit

# Restore a deleted file
git checkout HEAD -- path/to/deleted_file.py

# Reset a single file to last commit
git restore path/to/file.py

# Nuclear option — reset to match remote (DESTRUCTIVE)
git fetch origin
git reset --hard origin/main
```

> ⚠️ Never `reset --hard` or force-push to a shared branch.

---

## Stashing

```bash
# Stash dirty working tree
git stash                                         # stash tracked changes
git stash -u                                      # include untracked files
git stash push -m "WIP: patient search fix"       # named stash

# List stashes
git stash list

# Apply stash
git stash pop                                     # apply latest + drop it
git stash apply stash@{2}                         # apply specific, keep it

# Drop stash
git stash drop stash@{0}
git stash clear                                   # drop all stashes

# Create branch from stash
git stash branch feature/from-stash stash@{0}

# Show stash diff
git stash show -p stash@{0}
```

---

## Merging vs Rebasing

### Merge — preserves full history

```bash
git checkout main
git merge feature/my-feature                      # creates merge commit
git merge --no-ff feature/my-feature             # always create merge commit
git merge --squash feature/my-feature            # squash all into one commit
```

### Rebase — linear history (preferred for feature branches)

```bash
# Rebase feature branch onto main
git checkout feature/my-feature
git rebase main

# Interactive rebase — squash, reword, reorder commits
git rebase -i HEAD~3                              # last 3 commits
# Commands in editor:
# pick   = keep commit as-is
# reword = keep commit, edit message
# squash = meld into previous commit
# fixup  = like squash, discard message
# drop   = remove commit entirely

# Rebase onto remote main
git fetch origin
git rebase origin/main

# Abort a rebase in progress
git rebase --abort

# Continue after resolving conflicts
git rebase --continue
```

> 💡 Rule of thumb: **rebase local feature branches**, **merge to main/shared branches**.

---

## Cherry-pick

```bash
# Apply a single commit to current branch
git cherry-pick <commit-hash>

# Apply multiple commits
git cherry-pick abc123 def456

# Apply a range
git cherry-pick abc123^..def456

# Cherry-pick without committing (stage only)
git cherry-pick -n <commit-hash>

# Abort cherry-pick in progress
git cherry-pick --abort

# Continue after resolving conflicts
git cherry-pick --continue
```

---

## Remote Operations

```bash
# View remotes
git remote -v

# Add remote
git remote add origin https://github.com/njmarshall/ai-test-automation-python.git

# Change remote URL
git remote set-url origin git@github.com:njmarshall/ai-test-automation-python.git

# Fetch — download but don't merge
git fetch origin
git fetch --all                                   # all remotes
git fetch --prune                                 # remove deleted remote branches

# Pull
git pull                                          # fetch + merge
git pull --rebase                                 # fetch + rebase (cleaner)

# Push
git push origin feature/my-feature
git push -u origin feature/my-feature            # set upstream
git push --force-with-lease                       # safe force push (checks remote)
git push --tags                                   # push all tags

# Sync fork with upstream
git remote add upstream https://github.com/original/repo.git
git fetch upstream
git rebase upstream/main
```

---

## Tagging

```bash
# Lightweight tag
git tag v1.0.0

# Annotated tag (preferred — includes message, tagger, date)
git tag -a v1.0.0 -m "Release 1.0.0 — FHIR Phase 2 complete"

# Tag a specific commit
git tag -a v0.9.0 <commit-hash> -m "Beta release"

# List tags
git tag
git tag -l "v1.*"                                 # filter by pattern

# Push tags
git push origin v1.0.0                            # single tag
git push origin --tags                            # all tags

# Delete tag
git tag -d v1.0.0                                 # local
git push origin --delete v1.0.0                   # remote
```

---

## Log & Diff

```bash
# Log
git log
git log --oneline                                 # compact
git log --oneline --graph --all                   # branch graph
git log --oneline -10                             # last 10
git log --author="Neil"                           # filter by author
git log --since="2 weeks ago"
git log --grep="FHIR"                             # search commit messages
git log -- path/to/file.py                        # history of a file
git log -p                                        # show diffs inline

# Diff
git diff                                          # unstaged changes
git diff --staged                                 # staged changes
git diff main..feature/my-feature                # between branches
git diff HEAD~1 HEAD                              # last commit diff
git diff <hash1> <hash2>                          # between commits
git diff --name-only                              # files changed only
git diff --stat                                   # summary stats

# Show a commit
git show <commit-hash>
git show HEAD
git show HEAD:path/to/file.py                     # file at commit
```

---

## Bisect

Binary search through history to find the commit that introduced a bug.

```bash
# Start bisect
git bisect start

# Mark current as bad
git bisect bad

# Mark a known good commit
git bisect good v1.0.0
# Git checks out the midpoint — test it, then:

git bisect good    # if this commit is clean
git bisect bad     # if this commit has the bug

# Git narrows down — repeat until it identifies the culprit commit
# When done:
git bisect reset   # return to original HEAD

# Automate with a test script
git bisect start
git bisect bad HEAD
git bisect good v1.0.0
git bisect run pytest tests/test_patient.py       # auto-marks good/bad
git bisect reset
```

---

## Submodules

```bash
# Add a submodule
git submodule add https://github.com/org/shared-lib.git libs/shared

# Clone repo with submodules
git clone --recurse-submodules https://github.com/njmarshall/repo.git

# Initialize submodules after a plain clone
git submodule update --init --recursive

# Update submodules to latest
git submodule update --remote

# Remove a submodule
git submodule deinit libs/shared
git rm libs/shared
rm -rf .git/modules/libs/shared
```

---

## Aliases

Add to `~/.gitconfig` under `[alias]`:

```ini
[alias]
  st     = status
  co     = checkout
  sw     = switch
  br     = branch
  lg     = log --oneline --graph --all --decorate
  last   = log -1 HEAD --stat
  undo   = reset --soft HEAD~1
  unstage = restore --staged .
  aliases = config --get-regexp alias
  pushf  = push --force-with-lease
  sync   = !git fetch origin && git rebase origin/main
```

```bash
# Usage
git lg          # pretty branch graph
git undo        # undo last commit, keep changes staged
git sync        # fetch + rebase onto main in one shot
```

---

## Gotchas

### Never force-push to shared branches

```bash
# WRONG — rewrites shared history
git push --force origin main

# RIGHT — safe force push (fails if remote has new commits)
git push --force-with-lease origin feature/my-branch
```

### Detached HEAD state

```bash
# You're in detached HEAD when you checkout a commit hash directly
git checkout abc1234   # detached HEAD

# Save your work by creating a branch
git switch -c feature/save-my-work

# Or just go back
git switch main
```

### Merge conflict resolution

```bash
# After a conflict — edit the file, then:
git add <resolved-file>
git commit                                        # completes merge

# Or abort the merge entirely
git merge --abort

# Use a visual tool
git mergetool
```

### `.gitignore` not working (file already tracked)

```bash
# Remove file from tracking without deleting it
git rm --cached path/to/file
git rm --cached -r build/                         # directory

# Then commit the removal
git commit -m "chore: untrack build artifacts"
```

### Recover a dropped stash or lost commit

```bash
# Find dangling commits
git fsck --lost-found

# Or use reflog — Git's safety net
git reflog                                        # every HEAD movement
git checkout -b recovery-branch HEAD@{5}          # restore to that point
```

---

## Quick Reference Card

| Command | Purpose |
|---|---|
| `git status` | Working tree status |
| `git add -p` | Stage changes hunk-by-hunk |
| `git commit --amend` | Fix last commit |
| `git stash push -m "msg"` | Named stash |
| `git stash pop` | Apply + drop latest stash |
| `git rebase -i HEAD~3` | Interactive rebase last 3 |
| `git cherry-pick <hash>` | Apply single commit |
| `git log --oneline --graph --all` | Visual branch graph |
| `git bisect run <script>` | Auto-find bad commit |
| `git reflog` | Full HEAD history safety net |
| `git push --force-with-lease` | Safe force push |
| `git fetch --prune` | Sync + remove dead branches |
| `git restore --staged .` | Unstage everything |
| `git reset --soft HEAD~1` | Undo commit, keep staged |
| `git revert <hash>` | Safe undo for pushed commits |

---

*Part of the [ai-test-automation-python](https://github.com/njmarshall/ai-test-automation-python) daily playbooks*
