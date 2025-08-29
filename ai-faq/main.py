from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
import requests
import os
from dotenv import load_dotenv
from collections import Counter
import re

# Import database functions for SQLite
from database import get_db_connection, init_db

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
YOUR_SITE_URL = "http://localhost:8000" 
YOUR_APP_NAME = "FAQ Bot"

# --- FastAPI App Initialization ---
app = FastAPI()

@app.on_event("startup")
def on_startup():
    """Initialize the database when the application starts."""
    init_db()

# --- Pydantic Models ---
class Question(BaseModel):
    question: str

# --- API Endpoints ---
@app.post("/ask")
def ask_question(payload: Question):
    question = payload.question

    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY not configured.")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": YOUR_SITE_URL,
        "X-Title": YOUR_APP_NAME,
    }

    data = {
        "model": "deepseek/deepseek-chat-v3.1:free",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant who provides concise answers."},
            {"role": "user", "content": question}
        ]
    }

    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=data, timeout=30)
        response.raise_for_status() 

        resp_json = response.json()
        answer = resp_json.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not answer:
            answer = "Sorry, I received an empty answer from the API."

    except requests.exceptions.HTTPError as e:
        error_details = response.json().get("error", {}).get("message", response.text)
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {error_details}")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to connect to API: {e}")
    
    # Save the Q&A pair to the SQLite database
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Note: SQLite uses ? for placeholders, not %s
        query = "INSERT INTO faq (question, answer) VALUES (?, ?)"
        cursor.execute(query, (question, answer))
        conn.commit()
    except Exception as e:
        print(f"Database insert error: {e}")
    finally:
        conn.close()

    return {
        "question": question,
        "answer": answer,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/analytics")
def get_analytics():
    conn = get_db_connection()
    
    try:
        # 1. Total number of queries stored
        # The fetchone()[0] gets the first column of the first row
        total_queries = conn.execute("SELECT COUNT(*) FROM faq").fetchone()[0]

        # 2. Last 5 questions asked (with answers)
        # We fetch all rows using fetchall()
        last_5_rows = conn.execute("SELECT question, answer, created_at FROM faq ORDER BY id DESC LIMIT 5").fetchall()
        # FIX: Convert sqlite3.Row objects to standard dicts for the JSON response
        last_5_questions = [dict(row) for row in last_5_rows]

        # 3. Top 3 most frequent words across all questions
        all_questions_rows = conn.execute("SELECT question FROM faq").fetchall()
        
        word_list = []
        for row in all_questions_rows:
            # The conn.row_factory in database.py lets us access columns by name
            words_in_question = re.findall(r'\b\w+\b', row['question'].lower())
            word_list.extend(words_in_question)
        
        word_counts = Counter(word_list)
        top_words = word_counts.most_common(3)

        return {
            "total_queries": total_queries,
            "last_5_questions": last_5_questions,
            "top_3_words": [{"word": word, "count": count} for word, count in top_words]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing analytics: {e}")
    finally:
        # FIX: The conn object from sqlite3 does not have an is_connected method
        conn.close()