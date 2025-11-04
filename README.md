## How to run locally
### API service
```source .env && uvicorn api.main:app --reload```
### AI service
```source .env && celery -A celery_app.celery_app worker --loglevel=info -Q ai_queue```

## Run with Docker
- Build and launch the full stack (API, worker, MongoDB, Redis) with `docker compose up --build`.
- The FastAPI service is available at `http://localhost:8000`; MongoDB and Redis are exposed on the default ports for local tooling.
- Celery worker logs stream in the compose output; inspect them separately with `docker compose logs -f worker`.
- Model downloads from Hugging Face are cached in the named `huggingface-cache` volume so subsequent container runs reuse artifacts.
- To apply configuration changes (e.g., `AI_MODEL`, database URLs), edit the environment values inside `docker-compose.yml` before rebuilding.
