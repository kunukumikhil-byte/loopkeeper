# Push LoopKeeper to GitHub

1. Create a new empty repository on GitHub.
2. Open PowerShell inside this project folder.
3. Run:

```powershell
git init
git add .
git commit -m "Initial LoopKeeper release"
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

If GitHub asks you to authenticate, complete the browser/device authentication. Never put a GitHub password or token inside the source code.
