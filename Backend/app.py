from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from agent_controller import AgentController

load_dotenv()

app = FastAPI(title="Company Research Assistant")

# ✅ FIX 1 — Allow both origins
# Your frontend runs on http://localhost:5500
# but Chrome may internally send http://127.0.0.1:5500
ALLOWED_ORIGINS=[
    "http://localhost",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://127.0.0.1",
    "*"
],

# ✅ FIX 2 — CORS middleware must be defined IMMEDIATELY after app creation
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # allow ALL
    allow_credentials=True,
    allow_methods=["*"],        # allow POST, GET, OPTIONS
    allow_headers=["*"],        # allow Content-Type, Authorization, etc.
)


agent = AgentController()

# ===== MODELS =====
class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None

class EditSectionRequest(BaseModel):
    session_id: str
    section: str
    new_content: str

class DigRequest(BaseModel):
    session_id: str
    topic: str


# ===== ROUTES =====
@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        return agent.handle_message(req.message, req.session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/edit-section")
async def edit_section(req: EditSectionRequest):
    try:
        return agent.edit_section(req.session_id, req.section, req.new_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/dig-deeper")
async def dig_deeper(req: DigRequest):
    try:
        return agent.dig_deeper(req.session_id, req.topic)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}


# ✅ FIX 3 — ADD THIS to handle preflight OPTIONS request
@app.options("/chat")
def options_chat():
    return {}


@app.options("/edit-section")
def options_edit():
    return {}


@app.options("/dig-deeper")
def options_dig():
    return {}

@app.post("/reset")
def reset(session_id: str = "default-session"):
    agent.sessions.pop(session_id, None)
    return {"reply": "Session cleared. Start fresh!"}

@app.get("/")
def root():
    return {"message": "Company Research Assistant backend running"}

import logging
logging.basicConfig(level=logging.INFO)

@app.post("/chat")
async def chat(req: ChatRequest):
    logging.info(f"User said: {req.message}")
    response = agent.handle_message(req.message, req.session_id)
    return response
@app.post("/reset")
def reset_session():
    try:
        if "default-session" in agent.sessions:
            del agent.sessions["default-session"]
        return {"reply": "Session reset successfully."}
    except:
        return {"reply": "Session was already clear."}

