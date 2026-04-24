# AIOVA MongoDB - Quick Start

## 1️⃣ Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

## 2️⃣ Configure MongoDB

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env` and set your MongoDB connection:

**For Local MongoDB:**
```env
MONGO_URI=mongodb://localhost:27017
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
FRONTEND_ORIGIN=http://localhost:5173
```

**For MongoDB Atlas (Cloud):**
```env
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
FRONTEND_ORIGIN=http://localhost:5173
```

## 3️⃣ Start MongoDB (if local)

```bash
# Docker
docker run -d -p 27017:27017 --name mongodb mongo:latest

# Or native MongoDB
mongod
```

## 4️⃣ Start the Server

```bash
cd backend
uvicorn main:app --reload
```

✅ Server will auto-initialize the database on startup

## 5️⃣ Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173`

---

## Verify It Works

```bash
# Check API health
curl http://localhost:8000/health

# List interactions
curl -X POST http://localhost:8000/agent/invoke \
  -H "Content-Type: application/json" \
  -d '{"action":"list_entries"}'
```

---

## Database Details

- **Database:** `aivoa_db`
- **Collection:** `interactions`
- **Location:** Stored as MongoDB documents
- **ID Type:** ObjectId (returned as string in API)

---

**For detailed setup:** See `MONGODB_SETUP.md`
