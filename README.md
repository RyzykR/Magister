## How to run locally
### API service
```source .env && uvicorn api.main:app --reload```
### AI service
```source .env && celery -A celery_app.celery_app worker --beat --loglevel=info -Q ai_queue```
NOTE: celery requires Redis


## Tests
### Run Mongo test DB
```docker run --rm -it -p 27017:27017 mongo```
### Run tests
Run tests with Pytest by the command:
```pytest```
