# 🚀 Company Research Assistant — AI Agent (Eightfold.ai Assignment)

## This project is an AI-powered Research Assistant designed for the Eightfold.ai Agent-Building Assignment.
It is a fully functional conversational agent capable of researching companies, synthesizing data from multiple sources, detecting conflicting information, and generating structured, editable account plans.

The agent supports both chat and voice interaction, provides agentic behavior, handles multiple user personas, and features document retrieval, conflict detection, editable plan sections, and deep-dive research.

🌟 Features
###✅ 1. Multi-Source Company Research (RAG)

The agent:

Scrapes company websites

Reads Wikipedia pages

Collects contextual data from web results

Retrieves previously added documents

Uses a Retrieval-Augmented Generation (RAG) pipeline

Generates structured account plans (JSON schema enforced)

###✅ 2. Intelligent Agentic Behaviour

The agent is built to think and interact like a human assistant:

🔍 Conflict Detection

If contradictory data is found (e.g., revenue 4B vs 6B), the agent:

Warns the user

Shows conflict explanation

Offers a Dig Deeper button

Performs deeper research with additional retrieval rounds

🧠 Persona Detection

Agent automatically adapts tone & behavior:

Confused User: Provides guidance and suggests companies

Efficient User: Provides short summaries

Chatty User: Extracts company name from long messages

Normal Users: Responds regularly

✨ Smart Suggestion System

If user indirectly refers to a company (“I was reading about AI companies like OpenAI...”),
agent replies:
“You sound curious! Want me to research OpenAI for you?”

###✅ 3. Account Plan Editing (Interactive)

Each section of the generated plan has an Edit button.
Users can modify:

Snapshot

Market Opportunity

ICP

Stakeholders

Next Steps

Any nested field via dot-notation

The agent:

Re-summarizes the entire plan

Ensures consistency

Regenerates a correct JSON structure

###✅ 4. Voice Support 🎤

Users can interact via:

Text chat

Speech input through browser microphone

✅ 5. Frontend UI Highlights

Modern chat interface

Typing animation

Conflict warning banner

Dig deeper button

Edit modal

Progress logs in backend

Smooth scroll and clean message bubbles

Reset session button

###🏗️ Architecture Overview

This is the architecture used in the project:

1. Frontend (HTML/CSS/JS)

Chat UI

Voice recognition

Message typing animation

Conflict handler

Modal editor

REST API calls to backend

2. Backend (FastAPI + Python)

AgentController handles:

Intent detection

Persona detection

Formatting preference detection

RAG pipeline

Source scraping

Conflict detection

Deep-dive workflow

Editing workflow

Session state management

3. Retrieval System

Custom in-memory retriever

Stores scraped docs

Ranks & returns top context documents

4. LLM Layer

Uses OpenAI client for:

Generating account plans

Summaries (short / bullet / pitch)

Deep-dive research

Rewriting edited plans

5. Scraper

Lightweight HTML scraper

Extracts webpage text (fallback built-in)

##📂 Folder Structure
.
├── backend/
│   ├── agent_controller.py
│   ├── scraper.py
│   ├── retriever.py
│   ├── prompts.py
│   ├── app.py (FastAPI server)
│   └── .env
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
└── README.md

###📌 How It Works (Backend Logic Flow)
1. User sends a message → /chat

Agent performs:

Intent detection

Persona classification

Format detection

Company extraction

Source scraping

Retrieval + context building

LLM plan generation

Conflict detection

Sends structured response

2. If conflicts exist

Backend returns:

{
  "conflicts": {...},
  "reply": "I found conflicting information..."
}


Frontend displays a conflict banner + Dig deeper button.

3. If user edits

/edit-section triggers:

Plan update

LLM rewrite

Updated plan returned

🧪 Testing Scenarios (As Required by Assignment)
🤔 Confused User

“I don’t know what I want… help me decide.”
Agent suggests a company.

⚡ Efficient User

“Give me a short plan for Tesla.”
Agent provides a 3-line summary.

🗣️ Chatty User

“Yesterday I was reading about AI and OpenAI came to mind…”
Agent detects OpenAI and asks if user wants research.

🧪 Edge Case User

“Who are you?”

“Create plan for asdfghjkl”

“Give plan in bullets”

Agent responds gracefully.

🧵 API Endpoints
POST /chat
POST /edit-section
POST /dig-deeper
GET  /health

▶️ Running the Project
1. Start Backend
cd backend
uvicorn app:app --reload

2. Start Frontend
cd frontend
python -m http.server 5500

📦 Environment Variables

Create .env:

OPENAI_API_KEY=your-key
LLM_MODEL=gpt-4o-mini
FORCE_CONFLICT=false
