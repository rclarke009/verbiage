# Git sync situation (verbiage)

## What’s going on

1. **Nested repos**  
   - This workspace root is **conceptprojects** (remote: `ansible_demo`).  
   - **verbiage** has its own `.git` (remotes: `origin` = rclarke009/verbiage, `systems-eng` = rag-document-analysis-backend).  
   - The root repo also tracks `verbiage/` (including `app/config.py`), so the same files are in two repos. VS Code may run git in the root and show `app/config.py` there, which can make “sync” confusing.

2. **verbiage branch**  
   - In **verbiage** only: `main` is set to track `systems-eng/main`.  
   - Status: **ahead 9, behind 1** → 9 local commits not pushed, 1 remote commit not pulled.  
   - Until you integrate the remote commit, push may be rejected or require a merge.

## Fix verbiage sync (ahead 9, behind 1)

From the **verbiage** directory:

```bash
cd /path/to/conceptprojects/verbiage
git fetch systems-eng
git status   # confirm: ahead 9, behind 1
# Option A: merge (keeps a merge commit)
git pull systems-eng main
# Option B: rebase (linear history)
git pull --rebase systems-eng main
# Then push
git push systems-eng main
```

## Fix nested-repo confusion (optional)

Choose one:

- **Use only verbiage’s repo for verbiage**  
  Add to the **root** repo’s `.gitignore`:  
  `verbiage/`  
  Then in the root run:  
  `git rm -r --cached verbiage/`  
  Commit in conceptprojects. After that, the root repo no longer tracks verbiage; all verbiage sync is via `verbiage/.git` (systems-eng/origin).

- **Use only the root repo**  
  If verbiage should be part of conceptprojects only, remove its own git:  
  `rm -rf verbiage/.git`  
  Then all changes (including `app/config.py`) are only in conceptprojects and sync with ansible_demo.
