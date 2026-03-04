# Workflow: Connect GitHub

## Objective
Use GitHub as the remote for this project so you can push/pull code, use branches, and (optionally) automate with GitHub Actions.

## Prerequisites
- Git installed (you have it; repo is initialized).
- A GitHub account.
- (Optional) [GitHub CLI](https://cli.github.com/) (`gh`) for creating the repo from the terminal.

## Steps

### 1. Create a repository on GitHub
Choose one:

**Option A – GitHub website**
1. Go to [github.com/new](https://github.com/new).
2. Set **Repository name** (e.g. `Agent` or `d-Agent`).
3. Choose **Public** or **Private**.
4. Do **not** add a README, .gitignore, or license (project already has these).
5. Click **Create repository**.

**Option B – GitHub CLI**
```powershell
cd d:\Agent
gh auth login
gh repo create Agent --private --source=. --remote=origin --push
```
If the repo already exists: `gh repo create Agent --private --source=. --remote=origin` (then push when ready).

### 2. Add the remote (if you created the repo manually)
Replace `YOUR_USERNAME` and `REPO_NAME` with your GitHub username and repo name:
```powershell
cd d:\Agent
git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git
```

### 3. First commit and push
```powershell
cd d:\Agent
git add .
git status
git commit -m "Initial commit: WAT framework, tools, workflows"
git branch -M main
git push -u origin main
```

### 4. (Optional) Use SSH instead of HTTPS
If you use SSH keys with GitHub:
```powershell
git remote set-url origin git@github.com:YOUR_USERNAME/REPO_NAME.git
git push -u origin main
```

## Verify
- `git remote -v` — shows `origin` pointing to your GitHub repo.
- On GitHub: repo page shows your files and the initial commit.

## Notes
- `.env`, `credentials.json`, and `token.json` are in `.gitignore` and will not be pushed.
- For GitHub Actions or API use later, create a Personal Access Token (Settings → Developer settings → Personal access tokens) and store it in `.env` as `GITHUB_TOKEN`; never commit it.
