release: python -c "from backend.database import init_db; init_db()"
web: gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT backend.main:app
