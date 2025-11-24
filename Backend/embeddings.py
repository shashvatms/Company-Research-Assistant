import openai
import os
from dotenv import load_dotenv
load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
from openai import OpenAI
client = OpenAI()

def embed_texts(texts):
    model = os.getenv("EMBEDDINGS_MODEL")
    res = client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in res.data]
