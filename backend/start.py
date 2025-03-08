import uvicorn
from dotenv import load_dotenv
import os

load_dotenv()

if __name__ == "__main__":
    port = os.getenv("PORT", 8000)  # Use the PORT environment variable or default to 8000
    uvicorn.run("main:app", port=int(port))