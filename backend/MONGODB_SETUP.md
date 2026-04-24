# MongoDB Setup Guide for AIOVA

## Prerequisites

Before setting up MongoDB integration, ensure you have:
- MongoDB installed locally OR MongoDB Atlas account
- Python 3.10+
- Virtual environment activated

## Step 1: Install Dependencies

Install the required packages:

```bash
pip install -r requirements.txt
```

This includes:
- `pymongo` - MongoDB driver
- `python-dotenv` - Environment variable management

## Step 2: Configure MongoDB Connection

### Option A: Local MongoDB

1. **Start MongoDB locally**
   ```bash
   # On Windows (if installed)
   mongod
   
   # Or use Docker
   docker run -d -p 27017:27017 --name mongodb mongo:latest
   ```

2. **Update `.env` file**
   ```
   MONGO_URI=mongodb://localhost:27017
   ```

### Option B: MongoDB Atlas (Cloud)

1. **Create a cluster on MongoDB Atlas**
   - Go to https://www.mongodb.com/cloud/atlas
   - Sign up or log in
   - Create a new cluster

2. **Get your connection string**
   - In Atlas, click "Connect"
   - Copy the connection string
   - Replace `<password>` with your actual password

3. **Update `.env` file**
   ```
   MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
   ```

## Step 3: Initialize Database

The database will be initialized automatically when the FastAPI server starts:

```bash
uvicorn main:app --reload
```

This will:
- Create the `aivoa_db` database
- Create the `interactions` collection
- Create indexes on `hcp_name`, `date`, and `created_at`

## Database Schema

Each interaction is stored as a MongoDB document with the following structure:

```json
{
  "_id": "ObjectId",
  "hcp_name": "Dr. John Smith",
  "interaction_type": "Meeting",
  "date": "2026-04-24",
  "time": "14:30",
  "attendees": "Jane Doe, Mike Johnson",
  "topics": "Product efficacy, pricing",
  "materials": "Clinical reports, pricing sheet",
  "sentiment": "Positive",
  "outcomes": "Clinical discussion captured",
  "follow_up_actions": "Send clinical evidence and schedule follow-up",
  "created_at": "2026-04-24T14:30:00.000Z",
  "updated_at": "2026-04-24T15:00:00.000Z"
}
```

**Note:** When fetching data, `_id` is converted to `id` (as a string) for JSON compatibility.

## Available Database Functions

### List all interactions
```python
from database import list_interactions
entries = list_interactions()
```

### Get a single interaction
```python
from database import get_interaction
entry = get_interaction("507f1f77bcf86cd799439011")
```

### Create interaction
```python
from database import insert_interaction
new_entry = insert_interaction({
    "hcp_name": "Dr. Smith",
    "interaction_type": "Call",
    "date": "2026-04-25",
    "time": "10:00",
    "topics": "Follow-up discussion"
})
```

### Update interaction
```python
from database import update_interaction
updated = update_interaction("507f1f77bcf86cd799439011", {
    "sentiment": "Very Positive",
    "topics": "Extended discussion"
})
```

### Delete interaction (optional)
```python
from database import delete_interaction
success = delete_interaction("507f1f77bcf86cd799439011")
```

## Troubleshooting

### Connection Error: "Failed to connect to MongoDB"
- Ensure MongoDB is running (local) or accessible (Atlas)
- Check `MONGO_URI` in `.env` file
- Verify network connectivity to MongoDB server

### "ModuleNotFoundError: No module named 'pymongo'"
- Reinstall dependencies: `pip install -r requirements.txt`

### Slow queries
- Ensure indexes are created (happens automatically on init)
- Check MongoDB connection pool settings
- Monitor MongoDB server performance

## Testing

To verify MongoDB connection is working:

1. Start the server:
   ```bash
   uvicorn main:app --reload
   ```

2. Check health endpoint:
   ```bash
   curl http://localhost:8000/health
   ```

3. Create a test interaction:
   ```bash
   curl -X POST http://localhost:8000/agent/invoke \
     -H "Content-Type: application/json" \
     -d '{
       "action": "list_entries"
     }'
   ```

## Migration from SQLite

If you have existing SQLite data, you'll need to migrate it to MongoDB manually or using a migration script.

MongoDB documents are stored as JSON, making it easy to import data programmatically.

## Performance Tips

1. **Indexing:** Indexes on `hcp_name`, `date`, and `created_at` are created automatically
2. **Batch Operations:** For bulk inserts, consider batching multiple inserts
3. **Connection Pooling:** pymongo uses connection pooling automatically
4. **Query Optimization:** The duplicate detection uses optimized queries for performance

## Security

- **Never commit `.env` file** with real credentials
- Use environment variables for all sensitive data
- For MongoDB Atlas, use strong passwords and IP whitelisting
- Consider using database roles and permissions for production

---

For more info: https://docs.mongodb.com/
