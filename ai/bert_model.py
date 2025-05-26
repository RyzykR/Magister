import os
from transformers import pipeline
from dotenv import load_dotenv

load_dotenv()
model_name = os.getenv("AI_MODEL", "distilbert-base-uncased-finetuned-sst-2-english")

classifier = pipeline("zero-shot-classification", model=model_name)
