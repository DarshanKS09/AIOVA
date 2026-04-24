# 🚀 Production Deployment Guide

## Overview
This guide covers deploying AIOVA to production:
- **Frontend:** Vercel
- **Backend:** Render
- **Database:** MongoDB Atlas

---

## 🔐 Security Setup

### 1. **Secure Environment Variables**

**NEVER commit `.env` files** - they're in `.gitignore`

#### Backend (.env - DO NOT COMMIT)
```
# MongoDB - Use Atlas connection string
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/aivoa_db?retryWrites=true&w=majority

# OpenAI API Key
OPENAI_API_KEY=sk-xxx

# Production settings
ENV=production
FRONTEND_URL=https://your-frontend.vercel.app
```

#### Frontend (.env - DO NOT COMMIT)
```
VITE_API_BASE_URL=https://your-backend.onrender.com
```

---

## 📋 Pre-Deployment Checklist

- [ ] MongoDB Atlas account created and cluster ready
- [ ] OpenAI API key obtained
- [ ] Git repository clean (no uncommitted `.env` files)
- [ ] All tests passing
- [ ] Production environment variables documented

---

## 🎯 Backend Deployment (Render)

### Step 1: Prepare Repository

```bash
# Ensure .gitignore includes .env
git status
# Should NOT show .env files

# Commit all code
git add .
git commit -m "Production ready"
git push
```

### Step 2: Create Render Service

1. **Go to:** https://render.com/
2. **Click:** "New +" → "Web Service"
3. **Connect** your GitHub repository
4. **Configure:**
   - **Name:** aiova-backend
   - **Environment:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT backend.main:app`

### Step 3: Set Environment Variables on Render

Go to **Settings** → **Environment Variables**, add:

| Key | Value |
|-----|-------|
| `ENV` | `production` |
| `MONGO_URI` | `mongodb+srv://user:pass@cluster...` |
| `OPENAI_API_KEY` | `sk-...` |
| `FRONTEND_URL` | `https://your-frontend.vercel.app` |

### Step 4: Deploy

Click **Deploy** and wait for build completion.

**Backend URL:** `https://aiova-backend.onrender.com`

---

## 🎨 Frontend Deployment (Vercel)

### Step 1: Prepare Repository

```bash
# Ensure .env is in .gitignore
git status
# Should NOT show .env files

# Commit all code
git add .
git commit -m "Production ready"
git push
```

### Step 2: Connect to Vercel

1. **Go to:** https://vercel.com/
2. **Click:** "New Project"
3. **Import** your GitHub repository
4. **Select** the root directory: `/`

### Step 3: Configure Vercel Settings

**Build Settings:**
- **Framework:** Vite
- **Build Command:** `cd frontend && npm run build`
- **Output Directory:** `frontend/dist`
- **Install Command:** `npm install && cd frontend && npm install`

### Step 4: Set Environment Variables

Go to **Settings** → **Environment Variables**, add:

| Key | Value |
|-----|-------|
| `VITE_API_BASE_URL` | `https://aiova-backend.onrender.com` |

### Step 5: Deploy

Click **Deploy** and wait for build completion.

**Frontend URL:** `https://your-app.vercel.app`

---

## 🔒 Security Best Practices

### 1. **Environment Variables**
✅ Store all secrets in platform settings (Render, Vercel)
❌ Never commit `.env` files
❌ Never log sensitive data
✅ Use `.env.example` for documentation

### 2. **CORS Configuration**
✅ Production uses `ALLOWED_ORIGINS` from `FRONTEND_URL` environment variable
✅ Only `GET` and `POST` methods allowed
✅ Limited headers: `Content-Type` only

### 3. **API Security**
✅ Rate limiting recommended (add on Render)
✅ HTTPS enforced (both Render and Vercel use HTTPS)
✅ Debug mode disabled in production (`DEBUG=False`)

### 4. **Database Security**
✅ MongoDB Atlas IP whitelisting enabled
✅ Database-specific user with limited permissions
✅ Connection string uses strong password
✅ Encryption at rest enabled

### 5. **Git Security**
✅ `.env` files in `.gitignore`
✅ `.env.example` shows template (no real values)
✅ Sensitive files excluded from repository

---

## 📝 Environment Variables Reference

### Backend Required Variables

| Variable | Example | Purpose |
|----------|---------|---------|
| `MONGO_URI` | `mongodb+srv://...` | MongoDB connection |
| `OPENAI_API_KEY` | `sk-...` | OpenAI API access |
| `ENV` | `production` | Environment flag |
| `FRONTEND_URL` | `https://app.vercel.app` | CORS origin |

### Frontend Required Variables

| Variable | Example | Purpose |
|----------|---------|---------|
| `VITE_API_BASE_URL` | `https://api.onrender.com` | Backend API URL |

---

## 🧪 Testing Production Deployment

### Backend Health Check

```bash
curl https://aiova-backend.onrender.com/health
# Expected: {"status":"ok"}
```

### Test API Connection

```bash
curl -X POST https://aiova-backend.onrender.com/agent/invoke \
  -H "Content-Type: application/json" \
  -d '{"action":"list_entries"}'
```

### Frontend Connection

Visit: `https://your-app.vercel.app`

Test the full flow:
1. Fill form
2. Click "Save Entry"
3. Verify data persists in MongoDB

---

## 🔧 Troubleshooting

### Backend Issues

| Problem | Solution |
|---------|----------|
| "Failed to connect to MongoDB" | Check MONGO_URI in Render settings |
| CORS errors | Verify FRONTEND_URL matches Vercel deployment |
| 502 Bad Gateway | Check Render logs: `gunicorn` might be crashing |
| Cold start slow | Normal for free Render tier (pre-build service) |

### Frontend Issues

| Problem | Solution |
|---------|----------|
| "Cannot connect to API" | Verify VITE_API_BASE_URL is correct |
| Build fails on Vercel | Check Node.js version, npm install works locally |
| CORS errors | Backend ALLOWED_ORIGINS must include Vercel URL |

### MongoDB Issues

| Problem | Solution |
|---------|----------|
| Connection timeout | Whitelist Render IP in Atlas |
| Authentication failed | Verify username/password in MONGO_URI |
| Slow queries | Add indexes, check query performance |

---

## 📊 Monitoring & Logs

### Render Backend Logs

Go to **Dashboard** → **aiova-backend** → **Logs**

```
# Check for errors
# Should see: ✅ MongoDB initialized successfully
```

### Vercel Frontend Logs

Go to **Dashboard** → **aiova-frontend** → **Analytics** → **Functions**

### MongoDB Atlas

Go to **Cluster** → **Monitoring** to track:
- Query performance
- Connection count
- Storage usage

---

## 🔄 CI/CD Pipeline

### Automatic Deployment

Both Render and Vercel watch your GitHub repository:
- Push to `main` → Auto-deploy
- No manual intervention needed

### GitHub Actions (Optional)

Create `.github/workflows/deploy.yml` for advanced CI/CD:

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
      - run: pip install -r backend/requirements.txt
      - run: python -m pytest  # if you add tests
```

---

## 📱 Post-Deployment

### 1. **Monitor Performance**
- Check Render metrics
- Monitor MongoDB queries
- Track Vercel analytics

### 2. **Update DNS (Optional)**
If using custom domain:
- Vercel: Update DNS records
- Render: Update backend domain

### 3. **Backup Strategy**
- MongoDB Atlas: Enable automated backups
- GitHub: Regular commits
- Vercel: Deployment history available

### 4. **Update Documentation**
- Share production URLs with team
- Document deployment process
- Keep secrets secure

---

## 🎉 Success Indicators

✅ Backend running on Render
✅ Frontend running on Vercel
✅ MongoDB connected and initialized
✅ CORS working without errors
✅ Data persists after save
✅ No sensitive data in logs
✅ `.env` files excluded from git

---

## 🆘 Support

For issues:

1. **Render Docs:** https://render.com/docs
2. **Vercel Docs:** https://vercel.com/docs
3. **MongoDB Atlas:** https://docs.mongodb.com/atlas
4. **FastAPI:** https://fastapi.tiangolo.com/deployment/

---

**Production deployment complete!** 🚀
