import os
from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI


app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}
