# ☁️ Always-On Cloud Deployment Guide: ProfitBot Pro

Since Render's free tier "sleeps" during inactivity, we recommend using **Railway.app** or **Fly.io** for 24/7 background trading. These platforms ensure your bot is always running.

---

## **🚀 Option 1: Railway.app (Recommended - Easiest)**
Railway is very robust and won't sleep if you have a small amount of credit (the $5 trial credit is usually enough for a month).

### **Step-by-Step Instructions**
1.  **Push to GitHub**:
    -   Initialize Git: `git init`
    -   Add files: `git add .`
    -   Commit: `git commit -m "Always-on deployment ready"`
    -   Create a repo on GitHub and push: `git remote add origin YOUR_URL` then `git push -u origin main`
2.  **Deploy to Railway**:
    -   Log into [Railway.app](https://railway.app).
    -   Click **"New Project"** -> **"Deploy from GitHub repo"**.
    -   Select your repository.
3.  **Add Environment Variables** (Critical!):
    -   Go to the **Variables** tab in Railway and add:
        -   `STRATEGY`: `multitimeframe`
        -   `LEVERAGE`: `3`
        -   `MAX_TRADES`: `3`
        -   `AI_PROVIDER`: `gemini`
        -   `GEMINI_API_KEY`: `AIzaSyBAuL9zIKrA5aO89fRRYQs23c2zF2OSuYE`
        -   `PORT`: `5000`

---

## **🛸 Option 2: Fly.io (Professional - Singapore Region)**
Fly.io is great for running apps close to the exchange servers (like Singapore).

### **Step-by-Step Instructions**
1.  **Install Fly CLI**:
    -   Run this in PowerShell: `iwr https://fly.io/install.ps1 -useb | iex`
2.  **Login**:
    -   `fly auth login`
3.  **Deploy**:
    -   The `fly.toml` is already configured for you.
    -   Run: `fly launch` (Select "No" when asked to copy configuration, just use existing `fly.toml`).
    -   Run: `fly deploy`
4.  **Set Secrets**:
    -   `fly secrets set GEMINI_API_KEY=AIzaSyBAuL9zIKrA5aO89fRRYQs23c2zF2OSuYE`
    -   `fly secrets set STRATEGY=multitimeframe`

---

## **🛡️ Critical Checklist**
- **Persistent Storage**: Ensure you mount a volume for `/app/data` (Railway and Fly support this) to keep your `trade_history.json`.
- **Environment Tab**: Never put your real API keys in the code. Always use the cloud dashboard's "Variables" or "Secrets" tab.

---
*Updated on 2026-04-03*
