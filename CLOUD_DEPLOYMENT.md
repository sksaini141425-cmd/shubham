# ☁️ Cloud Deployment Guide: ProfitBot Pro

This guide explains how to move your bot from your local machine to the cloud (Render, Railway, or AWS) so it can run 24/7 without your computer being on.

---

## **1. Prerequisites**
- A **GitHub** account (free).
- A **Render.com** account (free tier available).
- Your Bybit API Keys.

---

## **2. Step-by-Step Instructions**

### **Step A: Push Code to GitHub**
1.  Initialize a Git repo in this folder: `git init`
2.  Add all files: `git add .`
3.  Commit: `git commit -m "Cloud deployment ready"`
4.  Create a new repository on GitHub.
5.  Push your code: `git remote add origin YOUR_URL` then `git push -u origin main`

### **Step B: Deploy to Render**
1.  Log into [Render.com](https://dashboard.render.com).
2.  Click **"New +"** and select **"Blueprint"**.
3.  Connect your GitHub repository.
4.  Render will automatically detect the [render.yaml](file:///c:/Users/sksai/OneDrive/Desktop/automated-trading-bot/render.yaml) file.
5.  Click **"Apply"**.

---

## **3. Critical: Environment Variables**
Once the deployment starts, go to the **Environment** tab in Render and add your secrets (never upload these to GitHub!):
- `BYBIT_API_KEY`: Your Bybit key.
- `BYBIT_API_SECRET`: Your Bybit secret.
- `GEMINI_API_KEY`: (Optional) For AI intelligence.
- `USE_REAL_EXCHANGE`: Set to `true` when you want real trading.

---

## **4. Persistent Data**
I have configured a **Persistent Disk** in the cloud settings. This ensures that your `trade_log.json` and balance history are **never lost**, even if the cloud server restarts.

---

## **5. Monitoring**
- Your dashboard will be available at a custom URL (e.g., `https://subham-profitbot.onrender.com`).
- You can access this URL from your phone or any computer to check your profits in real-time.

---
*Created on 2026-03-17*
