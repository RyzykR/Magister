## How to run locally
### API service
```source .env && uvicorn api.main:app --reload```
### AI service
```source .env && celery -A celery_app.celery_app worker --loglevel=info -Q ai_queue```