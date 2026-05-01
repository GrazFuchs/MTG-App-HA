# TODO: Git History Cleanup Required Before Public Release

## Problem
Personal data (`YourUsername`, `123456`) exists in git history (commit `36fc1b7b` and potentially others).

Even though these strings are removed from the current files, they remain accessible in the repository history.

## Required Action
Before switching the repository to public, run a history rewrite using `git filter-repo`:

```bash
# Install git-filter-repo (if not installed)
brew install git-filter-repo  # macOS
# or: pip install git-filter-repo

# Create a backup branch
git branch backup-before-filter

# Run the filter (replaces strings in ALL history)
git filter-repo --replace-text <(echo 'YourUsername==>YourUsername
123456==>123456')

# Force push to remote (DESTRUCTIVE - coordinate with collaborators!)
git push --force --all
git push --force --tags
```

## Verification After Cleanup
```bash
git log --all -p -S "YourUsername"  # Should return empty
git log --all -p -S "123456"     # Should return empty
```

## Warning
- This rewrites ALL commit hashes
- All collaborators must re-clone or reset their local repos
- Backup the repository before running filter-repo

## Reference
- [git-filter-repo documentation](https://github.com/newren/git-filter-repo)

---
**Delete this file after completing the history cleanup.**
