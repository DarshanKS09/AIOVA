# Testing Save Entry Flow - Step by Step Guide

## Prerequisites
- ✅ MongoDB is running (Atlas or local)
- ✅ Backend `.env` configured with `MONGO_URI`
- ✅ Backend running: `uvicorn main:app --reload`
- ✅ Frontend running: `npm run dev`

## Testing Checklist

### 1. **Verify Backend is Connected to MongoDB**

Check the console output when starting the backend:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
✅ MongoDB initialized successfully
```

If you see:
```
❌ Failed to initialize MongoDB: ...
```
Then MongoDB connection failed. Check:
- Is MongoDB running?
- Is `MONGO_URI` in `.env` correct?
- Can you ping the MongoDB server?

### 2. **Test Database Connectivity via API**

Run in terminal (PowerShell):
```powershell
# Check API health
curl -X GET http://localhost:8000/health

# List interactions (should be empty initially)
curl -X POST http://localhost:8000/agent/invoke `
  -H "Content-Type: application/json" `
  -d '{
    "action": "list_entries"
  }'
```

Expected response:
```json
{
  "status": "listed",
  "entries": [],
  "message": "Saved interactions loaded."
}
```

### 3. **Test Save Entry from Frontend**

1. **Open the app:** `http://localhost:5173`

2. **Fill in the form** on the left:
   - HCP Name: `Dr. John Smith`
   - Interaction Type: `Meeting`
   - Date: `2026-04-24`
   - Time: `14:30`
   - Attendees: `Jane Doe`
   - Topics: `Product efficacy`
   - Materials: `Clinical reports`

3. **Click "Save Entry" button**
   
4. **Check the Chat** (right side):
   - Should see: `"Checking saved interactions for duplicates."`
   - Then: `"Generating follow-up suggestions before saving."`
   - Finally: `"Interaction saved successfully."`

5. **Verify Entry is Saved:**
   - Form should be cleared (or show the saved entry)
   - Entries list should update

### 4. **Verify Data is in MongoDB**

```powershell
# List interactions again
curl -X POST http://localhost:8000/agent/invoke `
  -H "Content-Type: application/json" `
  -d '{
    "action": "list_entries"
  }'
```

You should now see your saved interaction with:
- `id`: MongoDB ObjectId (as string)
- `hcp_name`: "Dr. John Smith"
- `date`: "2026-04-24"
- `sentiment`: "Neutral" (auto-generated)
- `outcomes`: "Follow-up pending." (auto-generated)
- `created_at`: timestamp
- etc.

### 5. **Test Duplicate Detection**

1. **Save the same entry again** with same HCP name and date

2. **Expected behavior:**
   - Should detect as potential duplicate
   - Message: `"Duplicate interaction detected. Do you want to merge or save as new?"`
   - Should show 2 buttons: `Merge` or `Save as New`

3. **Test Merge:**
   - Click `Merge` button
   - Should merge the data into existing record
   - Chat: `"Duplicate interaction merged successfully."`

4. **Test Save as New:**
   - Save the same data again
   - When duplicate detected, click `Save as New`
   - Should save as separate entry
   - Chat: `"Interaction saved as a new record."`

### 6. **Test Data Persistence**

1. **Refresh the page** (F5 or Cmd+R)

2. **Check:**
   - All saved interactions should still appear
   - Data is persisted in MongoDB

## Expected Save Entry Flow (Technical)

```
Frontend (Save Entry)
    ↓
POST /agent/invoke
  - action: "save_entry"
  - form_data: {...}
    ↓
Backend Agent:
  Step 1: DuplicateCheckTool
    - Queries MongoDB: list_interactions()
    - Compares against new entry
    - Returns: is_duplicate (true/false)
    ↓
  If duplicate found:
    - Return response with status: "duplicate_detected"
    - Frontend shows Merge/Save As New buttons
    ↓
  If no duplicate:
    Step 2: FollowUpSuggestionTool
      - Generates sentiment, outcomes, follow_up_actions
    ↓
    Step 3: LogInteractionTool (operation: "save")
      - Calls: insert_interaction(entry)
      - MongoDB: collection.insert_one(document)
      - Returns: saved document with _id converted to id
    ↓
    Step 4: Return response
      - status: "saved"
      - entry: saved data
      - entries: all interactions
      - message: "Interaction saved successfully."
    ↓
Frontend:
  - Update form
  - Refresh entries list
  - Display success message
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **"I couldn't save the interaction right now"** | Check backend logs. MongoDB connection likely failed. |
| **Empty entries list after save** | Check MongoDB is running. Check MONGO_URI in .env |
| **Duplicate detection not working** | Make sure MongoDB has data. Check duplicate logic in heuristic_duplicate_check(). |
| **Saved entry missing fields** | Check form validation. All fields should be strings. |
| **502 Bad Gateway** | Backend crashed. Check logs. Likely database connection error. |

## MongoDB Data Structure

Each saved interaction looks like:
```json
{
  "_id": "507f1f77bcf86cd799439011",
  "id": "507f1f77bcf86cd799439011",
  "hcp_name": "Dr. John Smith",
  "interaction_type": "Meeting",
  "date": "2026-04-24",
  "time": "14:30",
  "attendees": "Jane Doe",
  "topics": "Product efficacy",
  "materials": "Clinical reports",
  "sentiment": "Neutral",
  "outcomes": "Follow-up pending.",
  "follow_up_actions": "Send a follow-up summary and confirm next steps.",
  "created_at": "2026-04-24T14:30:00.000Z"
}
```

## Success Indicators ✅

- [ ] Backend shows `✅ MongoDB initialized successfully`
- [ ] `/health` endpoint returns `{"status": "ok"}`
- [ ] Can list entries (even if empty)
- [ ] Form data saves to MongoDB
- [ ] Saved entries appear in list
- [ ] Duplicate detection works
- [ ] Data persists after page refresh
- [ ] All entries have `id`, `created_at` fields

---

**If everything is working, the save flow is complete!** 🎉
