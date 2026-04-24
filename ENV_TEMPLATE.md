# Production Environment Variables Template
# ⚠️  DO NOT COMMIT THIS FILE - This is for documentation only
# Create actual .env file locally or in your deployment platform (Render/Vercel)

# === BACKEND ===

# MongoDB Atlas connection string
# Get from: https://www.mongodb.com/cloud/atlas
# Format: mongodb+srv://username:password@cluster-name.mongodb.net/database?retryWrites=true&w=majority
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority

# OpenAI API Key
# Get from: https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-your_api_key_here

# OpenAI Model
OPENAI_MODEL=gpt-4o-mini

# Environment mode (development or production)
ENV=production

# Frontend URL (for CORS)
# Set to your Vercel frontend URL
FRONTEND_URL=https://your-app.vercel.app

# === FRONTEND ===

# Backend API URL
# Set to your Render backend URL
VITE_API_BASE_URL=https://your-backend.onrender.com

# === LOCAL DEVELOPMENT (different .env file) ===

# For local development, create a separate .env file:
# ENV=development
# MONGO_URI=mongodb://localhost:27017
# FRONTEND_URL=http://localhost:5173
# VITE_API_BASE_URL=http://localhost:8000

# === SECURITY NOTES ===

# 1. MONGO_URI should point to MongoDB Atlas (not local)
# 2. OPENAI_API_KEY: Keep this SECRET - never share publicly
# 3. FRONTEND_URL: Must match your Vercel deployment domain
# 4. VITE_API_BASE_URL: Must match your Render deployment domain
# 5. Never commit actual values - only use in platform settings

# === INSTRUCTIONS ===

# For Render Backend:
# 1. Go to Dashboard → Settings → Environment Variables
# 2. Add each variable from the "BACKEND" section above
# 3. Use actual values, not placeholders

# For Vercel Frontend:
# 1. Go to Project Settings → Environment Variables
# 2. Add each variable from the "FRONTEND" section above
# 3. Use actual values, not placeholders

# To get values:
# 1. MongoDB URI: MongoDB Atlas → Cluster → Connect → Get connection string
# 2. OpenAI API Key: https://platform.openai.com/api-keys
# 3. Frontend URL: From Vercel deployment
# 4. Backend URL: From Render deployment
