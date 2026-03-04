# Workflow: 將 site 出街 (Deploy site)

## Objective
把 `D:\Agent\site` 嘅靜態網站部署上線，經 **GitHub Pages** 或 **Netlify** 提供公開 URL。

---

## 方法一：GitHub Pages（已設定好 Action）

### 1. 喺 GitHub 開 Pages
1. 將專案 push 去 GitHub（若未做：見 `workflows/setup/github_setup.md`）。
2. 去 Repo → **Settings** → **Pages**。
3. **Build and deployment** → **Source** 選 **GitHub Actions**。
4. 儲存後，每次 push `main` 且改動到 `site/` 或本 workflow 時，會自動部署。

### 2. 第一次部署
Push 一次就會觸發：
```powershell
cd d:\Agent
git add .
git commit -m "Add site and deploy workflow"
git push origin main
```
完成後，喺 **Settings → Pages** 會顯示 site URL，通常係：  
`https://<你的username>.github.io/<repo名>/`

### 3. 影片檔 (assets/video.mp4)
`index.html` 會載入 `site/assets/video.mp4`。若未放影片：
- 將 `video.mp4` 放到 `site/assets/`，再 commit + push；或
- 影片太大可改用外部連結（例如 YouTube 嵌入或 CDN），再改 `index.html` 嘅 `src`。

---

## 方法二：Netlify（可選，有自己 domain 時好用）

1. 去 [netlify.com](https://www.netlify.com/) 登入，**Add new site** → **Import an existing project**。
2. 連 GitHub，揀呢個 repo。
3. **Build settings**：
   - **Base directory:** `site`（或留空若你 build 產出喺 repo root）。
   - **Publish directory:** 若 Base 係 `site`，Publish 填 `.` 或留空。
4. Deploy 後會有一個 `xxx.netlify.app` URL，可再綁自己 domain。

---

## 檢查清單
- [ ] Repo 已 push 上 GitHub  
- [ ] Settings → Pages → Source = **GitHub Actions**  
- [ ] 至少 push 一次（或手動 Run workflow）  
- [ ] 需要影片時：`site/assets/video.mp4` 已加入並 push  

完成後，site 就會出街。
