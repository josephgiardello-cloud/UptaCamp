# Repository Hygiene Playbook

## 1) Remove historical artifacts from Git history

Use BFG Repo-Cleaner (recommended for speed):

```powershell
# Backup first
Copy-Item .git .git.backup -Recurse

# Run from repository root after downloading bfg.jar
java -jar bfg.jar --delete-files "*.db" --delete-files "*.pkl" --delete-files "*.onnx" .git

git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push --force
```

Alternative with git filter-repo:

```powershell
git filter-repo --path-glob "*.db" --path-glob "*.pkl" --path-glob "*.onnx" --invert-paths
git push --force
```

## 2) Enable Git LFS

```powershell
git lfs install
git lfs track "*.onnx" "*.onnx.json" "*.pkl" "*.pt" "*.h5" "*.ckpt" "*.tflite" "*.pb"
git add .gitattributes
git commit -m "chore: track large model artifacts with git lfs"
```

## 3) Enforce no-artifact commits

```powershell
pre-commit install
pre-commit run --all-files
```

## 4) Data directory policy

Generated databases, logs, checkpoints, and local cache files belong under `data/` and must remain untracked.
