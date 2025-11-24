# backend/agent_controller.py
import os
import json
import time
import re
from dotenv import load_dotenv
from retriever import retriever
from scraper import scrape_url
from prompts import RAG_PROMPT, ACCOUNT_PLAN_SCHEMA
from openai import OpenAI

load_dotenv()

# Local uploaded image path (you previously uploaded this file)
UPLOADED_IMAGE_PATH = "/mnt/data/255b1193-876b-44ba-ac3c-26616b4008e3.png"

# Helper: simple competitor hints (extend as needed)
DEFAULT_COMPETITORS = {
    "zoom": ["Microsoft Teams", "Google Meet", "Cisco Webex"],
    "openai": ["Anthropic", "Cohere", "Google DeepMind"],
    "tesla": ["Ford", "GM", "BYD"],
    "meta": ["Google", "Snap", "TikTok"]
}

class AgentController:
    def __init__(self):
        # OpenAI client
        self.client = OpenAI()
        # session state map: session_id -> plan JSON + metadata
        self.sessions = {}  # e.g. {session_id: {"plan":..., "sources":..., "pending_conflict":..., ...}}
        # Demo helper: environment toggle to force conflicts
        self.force_conflict = os.getenv("FORCE_CONFLICT", "false").lower() in ("1", "true", "yes")

    # ----------------- Utility helpers -----------------
    def safe_llm_call(self, messages, max_retries=4, temperature=0.2, max_tokens=1200):
        """Reliable wrapper for OpenAI API calls with retry + exponential backoff."""
        delay = 1

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                return response

            except Exception as e:
                err = str(e).lower()

                # 429 or overload → retry
                if "rate limit" in err or "429" in err or "overloaded" in err:
                    if attempt == max_retries - 1:
                        return None  # final fail
                    time.sleep(delay)
                    delay *= 2
                    continue

                # Other error → no retry
                print("LLM ERROR:", e)
                return None

        return None
    def _progress(self):
        """Create a new progress list for a request."""
        return []

    def _add_progress(self, progress_list, message):
        progress_list.append({"ts": time.time(), "msg": message})

    def detect_persona(self, message: str) -> str:
        """Detect simple persona from message text."""
        m = message.lower()
        if any(w in m for w in ["don't know", "not sure", "help me", "i'm confused", "what should"]):
            return "confused"
        if any(w in m for w in ["short", "quick", "tl;dr", "summary", "brief"]):
            return "efficient"
        if len(m.split()) > 30 or any(w in m for w in ["story", "so anyway", "by the way", "btw"]):
            return "chatty"
        return "unknown"

    def detect_format(self, message: str) -> str:
        """Detect requested output format: short/detailed/pitch/bullets."""
        m = message.lower()
        if any(w in m for w in ["pitch", "investor", "one-pager"]):
            return "pitch"
        if any(w in m for w in ["short", "brief", "summary", "tl;dr"]):
            return "short"
        if any(w in m for w in ["bullet", "bullets", "list"]):
            return "bullets"
        return "detailed"

    def extract_company(self, message: str) -> str:
        """Naive extraction: 'for <company>' or last proper noun-like word."""
        words = message.split()
        if "for" in words:
            idx = words.index("for")
            if idx + 1 < len(words):
                candidate = words[idx + 1].strip().strip(".,!?")
                # remove common words accidentally picked
                if candidate.lower() not in ["me", "us", "that", "this"]:
                    return re.sub(r'[^A-Za-z0-9\-]', '', candidate)
        # fallback: try last word
        last = words[-1].strip().strip(".,!?")
        return re.sub(r'[^A-Za-z0-9\-]', '', last) or "UnknownCompany"

    def add_sources(self, session_id, urls=None, local_files=None, progress=None):
        """Scrape URLs and add docs to retriever. Returns list of sources added."""
        sources = []
        if urls:
            for url in urls:
                try:
                    if progress is not None:
                        self._add_progress(progress, f"Scraping {url}...")
                    scraped = scrape_url(url)
                    text = scraped.get("text", "") or ""
                    title = scraped.get("title") or url
                    doc = {"url": url, "title": title, "text": text}
                    # add to retriever (assumes retriever.add exists)
                    try:
                        retriever.add(doc)
                    except Exception:
                        # maintaining compatibility: some retrievers call add_doc
                        if hasattr(retriever, "add_doc"):
                            retriever.add_doc(doc)
                        else:
                            # fallback: append to internal list if present
                            if hasattr(retriever, "docs"):
                                retriever.docs.append(doc)
                    sources.append({"url": url, "title": title, "date": ""})
                    if progress is not None:
                        self._add_progress(progress, f"Added source: {url}")
                except Exception as e:
                    if progress is not None:
                        self._add_progress(progress, f"Failed to scrape {url}: {str(e)}")
        if local_files:
            for lf in local_files:
                title = lf.get("title", "local-file")
                doc = {"url": lf.get("url", ""), "title": title, "text": lf.get("text", "")}
                try:
                    retriever.add(doc)
                except Exception:
                    if hasattr(retriever, "add_doc"):
                        retriever.add_doc(doc)
                    elif hasattr(retriever, "docs"):
                        retriever.docs.append(doc)
                sources.append({"url": lf.get("url"), "title": title, "date": lf.get("date", "")})
                if progress is not None:
                    self._add_progress(progress, f"Added local source: {title}")
        return sources

    def get_retrieved_context(self, progress=None):
        """Return a combined context string built from top retrieved docs."""
        try:
            docs = retriever.get_top()
        except Exception:
            # compatibility: some retrievers provide docs attribute
            docs = getattr(retriever, "docs", [])[:5]
        context_pieces = []
        for d in docs:
            title = d.get("title", d.get("url", "source"))
            text = d.get("text", "")[:2000]
            context_pieces.append(f"[{title} | {d.get('url','')}] \n{text}")
        if progress is not None:
            self._add_progress(progress, f"Built context from {len(context_pieces)} docs.")
        return "\n\n".join(context_pieces), docs

    def detect_competitors(self, company: str):
        key = company.lower()
        return DEFAULT_COMPETITORS.get(key, [])

    # ----------------- Intent / Main handler -----------------
    def detect_intent(self, message: str):
        msg = message.lower().strip()

        # CHATTY user should override greeting
        if len(msg.split()) > 12:  
            return "chatty"

        # Confused user
        if any(w in msg for w in [
            "i don't know", 
            "not sure", 
            "help me figure",
            "no idea"
        ]):
            return "confused"

        # Greeting detection
        if any(w in msg for w in ["hello", "hi", "hey", "hlo"]):
            return "greeting"

        # Smalltalk / who are you
        if any(w in msg for w in ["who are you", "how are you", "what's up"]):
            return "smalltalk"

        # Efficient/quick user
        if any(w in msg for w in ["short", "brief", "quick", "tl;dr"]):
            return "efficient"

        # Account plan intent
        if any(w in msg for w in ["account plan", "create", "generate", "research"]):
            return "account_plan"

        return "unknown"


    def handle_message(self, message, session_id=None):
        session_id = session_id or "anon"
        msg = message.lower().strip()

        # If pending conflict — keep same logic
        session = self.sessions.get(session_id, {})
        pending_topic = session.get("pending_conflict")

        if pending_topic:
            if msg in ["yes", "go ahead", "dig deeper", "yes please"]:
                session.pop("pending_conflict", None)
                return self.dig_deeper(session_id, pending_topic)
            elif msg in ["no", "skip"]:
                session.pop("pending_conflict", None)
                return {"reply": "Okay, skipping deep research.", "account_plan": session.get("plan")}
            else:
                return {"reply": f"Say 'yes' to dig deeper into {pending_topic} or 'no' to skip."}

        session = self.sessions.setdefault(session_id, {})

        # Check if user is responding to suggestion
        if "pending_suggestion" in session:
            suggested_company = session["pending_suggestion"]

            if msg in ["yes", "yeah", "yep", "sure", "go ahead", "do it", "please do"]:
                # User accepted
                session.pop("pending_suggestion", None)
                return self.generate_plan(f"create an account plan for {suggested_company}", session_id)

            elif msg in ["no", "no thanks", "not now"]:
                session.pop("pending_suggestion", None)
                return {"reply": "Okay! Let me know if you want to research another company."}

            # User said something else → remind them
            return {
                "reply": f"Should I research {suggested_company}? Say yes or no."
            }

        
        # Persona detection
        intent = self.detect_intent(message)
        print("DETECTED INTENT:", intent)

        if intent == "greeting":
            return {"reply": "👋 Hello! Tell me a company name, e.g. 'Create an account plan for Zoom'."}

        if intent == "smalltalk":
            return {"reply": "I'm good — ready to research. Tell me a company."}

        if intent == "confused":
            return {"reply": "No worries. I can research any company and generate an account plan. Want to try something like: 'Create an account plan for Tesla'?"}

        if intent == "chatty":
            company = self.extract_company_name(message)  # we'll define this below

            if company:
                self.sessions[session_id]["pending_suggestion"] = company
                return {
                    "reply": f"You sound curious! It seems you're interested in {company}. Want me to research it for you?"
                }

            return {"reply": "You sound curious! Tell me a company you'd like to explore."}

        if intent == "efficient":
            return {"reply": "Got it — I can make a short version. Tell me: 'Create a short account plan for <company>'."}

        if intent == "account_plan":
            return self.generate_plan(message, session_id)

        # Unknown fallback
        return {"reply": "I can generate account plans. Try: 'Create an account plan for Zoom'."}

    def extract_company_name(self, msg: str):
        companies = ["openai", "zoom", "tesla", "meta", "google", "nvidia", "microsoft"]
        for c in companies:
            if c in msg.lower():
                return c.capitalize()
        return None

    
    # ----------------- Plan generation -----------------
    def generate_plan(self, message, session_id, persona="unknown", out_format="detailed"):
        session_id = session_id or "anon"
        progress = self._progress()
        if session_id in self.sessions:
            self.sessions[session_id].pop("pending_conflict", None)
        self._add_progress(progress, "Received request, detecting company and preferences...")
        company = self.extract_company(message)
        self._add_progress(progress, f"Detected company: {company}")

        # detect competitors & format
        competitors = self.detect_competitors(company)
        if competitors:
            self._add_progress(progress, f"Found competitors: {', '.join(competitors)}")

        # seed urls to scrape
        seed_urls = [
            f"https://{company}.com",
            f"https://www.{company}.com",
            f"https://en.wikipedia.org/wiki/{company}"
        ]
        self._add_progress(progress, "Preparing seed sources for scraping...")

        # include uploaded file as local source (use your provided path)
        local_files = [
            {"url": UPLOADED_IMAGE_PATH, "title": f"{company} - uploaded file", "text": "", "date": ""}
        ]

        # Add sources (scrape + local)
        sources_added = self.add_sources(session_id, urls=seed_urls, local_files=local_files, progress=progress)

        # retrieve top docs and build context
        context, docs = self.get_retrieved_context(progress=progress)

        # Build RAG prompt
        rag_prompt = RAG_PROMPT.format(context=context, request=message, schema=ACCOUNT_PLAN_SCHEMA)

        # Include a short system prompt with persona-awareness and output formatting instruction
        system_msg = {
            "role": "system",
            "content": (
                "You are ResearchGPT — produce a structured account plan in JSON following the schema. "
                f"User persona: {persona}. Output preference: {out_format}. If asked, provide a short summary, pitch, or bullets. "
                "If facts conflict across sources, include a 'conflicts' field listing the differing values and their sources."
            )
        }

        user_msg = {"role": "user", "content": rag_prompt}
        self._add_progress(progress, "Calling LLM to generate account plan...")

        # Call the LLM
        try:
            response = self.safe_llm_call(
                messages=[system_msg, user_msg],
                temperature=0.2,
                max_tokens=1200
            )

            if response is None:
                return {
                    "reply": "⚠️ The AI is temporarily overloaded. Please try again in 5–10 seconds.",
                    "account_plan": None,
                    "progress": progress,
                    "sources": sources_added
                }

            text = response.choices[0].message.content

            self._add_progress(progress, "Received response from LLM.")
        except Exception as e:
            self._add_progress(progress, f"LLM call failed: {str(e)}")
            # return partial progress and error
            return {"reply": "Failed to generate plan via LLM.", "error": str(e), "progress": progress, "sources": sources_added}

        # parse/clean potential triple-backticked JSON
        clean = text
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?", "", clean, flags=re.IGNORECASE).rstrip("`").strip()

        parsed = None
        try:
            parsed = json.loads(clean)
        except Exception:
            # fallback: put raw text into snapshot.raw_output
            parsed = {"raw_output": text}

        # Persist session
        self.sessions[session_id] = {
            "plan": parsed,
            "sources": sources_added or [],
            "last_query": message,
            "timestamp": time.time()
        }

        # Quick fact extraction for conflict heuristic (revenue/employees)
        facts = []
        try:
            snap = parsed.get("snapshot", {})
            if snap:
                facts.append(("revenue", str(snap.get("revenue_estimate")), "generated"))
                facts.append(("employees", str(snap.get("employees_estimate")), "generated"))
        except Exception:
            pass

        # If forced conflict mode is ON, simulate a conflict (useful for demos)
        if self.force_conflict:
            fake_conflicts = {
                "revenue": [
                    {"value": "4B", "sources": ["Wikipedia"]},
                    {"value": "6B", "sources": ["News report"]}
                ]
            }
            topic = "revenue"
            self.sessions[session_id]["pending_conflict"] = topic
            self._add_progress(progress, "Forced conflict mode ON: simulating conflict on revenue.")
            return {
                "reply": f"I found conflicting information about {topic}. Should I dig deeper?",
                "account_plan": parsed,
                "conflicts": fake_conflicts,
                "progress": progress,
                "sources": sources_added,
                "format": out_format
            }

        # Heuristic conflict detection: if different values exist across retrieved docs
        conflicts = {}
        # Very naive: look inside docs text for revenue/employee patterns and compare
        def find_numeric_in_text(patterns, docs):
            found = {}
            for doc in docs:
                txt = (doc.get("text") or "").lower()
                src = doc.get("url") or doc.get("title") or "source"
                for pat in patterns:
                    match = re.search(pat, txt)
                    if match:
                        val = match.group(1).strip()
                        found.setdefault(val, []).append(src)
            return found

        # patterns to extract simple numbers like "$123 billion" or "127,000 employees"
        revenue_patterns = [r"\$([\d\.,]+\s?(?:billion|million|bn|m|B|M))", r"revenue(?:\s*[:\-]?\s*)([\d\.,]+\s?(?:billion|million|bn|m))"]
        employees_patterns = [r"([\d\.,]+\s?employees)", r"([\d\.,]+\s?staff)"]

        rev_found = find_numeric_in_text(revenue_patterns, docs)
        emp_found = find_numeric_in_text(employees_patterns, docs)

        if len(rev_found.keys()) > 1:
            conflicts["revenue"] = [{"value": v, "sources": s} for v, s in rev_found.items()]
        if len(emp_found.keys()) > 1:
            conflicts["employees"] = [{"value": v, "sources": s} for v, s in emp_found.items()]

        if conflicts:
            topic = list(conflicts.keys())[0]
            self.sessions[session_id]["pending_conflict"] = topic
            self._add_progress(progress, f"Detected conflicts on {topic}. Asking user to dig deeper.")
            return {
                "reply": f"I found conflicting information about {topic}. Should I dig deeper?",
                "account_plan": parsed,
                "conflicts": conflicts,
                "progress": progress,
                "sources": sources_added,
                "format": out_format
            }

        # No conflicts -> produce final response. Also produce alternative condensed formats if requested
        summary_text = None
        try:
            # If user wanted a short/pitch/bullets format, ask the LLM for a condensed version
            if out_format in ("short", "pitch", "bullets"):
                self._add_progress(progress, f"Generating {out_format} version of the plan...")
                short_prompt = (
                    f"Given the following account plan JSON:\n{json.dumps(parsed)}\n\n"
                    + ("Provide a concise 3-line summary." if out_format == "short" else
                       "Provide a pitch-style one-paragraph summary." if out_format == "pitch" else
                       "Provide the plan as 6 concise bullet points.")
                )
                short_resp = self.safe_llm_call(
                    messages=[{"role":"system","content":"You are a summarizer."},
                            {"role":"user","content":short_prompt}],
                    temperature=0.2,
                    max_tokens=300
                )

                if short_resp:
                    summary_text = short_resp.choices[0].message.content

                self._add_progress(progress, f"Generated {out_format} version.")
        except Exception as e:
            self._add_progress(progress, f"Failed to generate condensed format: {str(e)}")
            summary_text = None

        self._add_progress(progress, "Completed plan generation.")

        response = {
            "reply": f"Generated account plan for {company}.",
            "account_plan": parsed,
            "progress": progress,
            "sources": sources_added,
            "format": out_format,
        }
        if summary_text:
            response["summary"] = summary_text

        return response

    # ----------------- Dig deeper -----------------
    def dig_deeper(self, session_id, topic):
        session_id = session_id or "anon"
        session = self.sessions.get(session_id)
        if not session:
            return {"reply": "Session not found. Generate an account plan first."}

        progress = self._progress()
        self._add_progress(progress, f"Starting deep-dive on {topic}...")

        # Expanded sources (demo): news, sec filings (placeholder)
        extra_urls = [
            f"https://www.google.com/search?q={topic}+{session.get('last_query','')}",
            f"https://news.google.com/search?q={topic}+{session.get('last_query','')}"
        ]
        self._add_progress(progress, "Adding deeper sources...")
        self.add_sources(session_id, urls=extra_urls, progress=progress)

        # rebuild context
        context, docs = self.get_retrieved_context(progress=progress)

        prompt = (
            "You are doing a deeper research for the specific topic: " + topic + "\n\n"
            + "Context:\n" + context + "\n\n"
            + "Task: Re-evaluate and reconcile conflicting facts about " + topic + ". Provide the most likely value and cite sources. "
            + "If still uncertain, indicate uncertainty and list differing sources."
        )

        self._add_progress(progress, "Calling LLM for reconciliation...")
        try:
            response = self.safe_llm_call(
                messages=[
                    {"role":"system","content":"You are a research assistant that reconciles facts using new context."},
                    {"role":"user","content":prompt}
                ],
                max_tokens=500
            )

            if response is None:
                return {
                    "reply": "⚠️ Deep-dive failed due to model overload. Try again shortly.",
                    "progress": progress
                }

            text = response.choices[0].message.content

            self._add_progress(progress, "Completed deep-dive and reconciliation.")
        except Exception as e:
            self._add_progress(progress, f"Deep-dive LLM call failed: {str(e)}")
            return {"reply": "Deep-dive failed.", "error": str(e), "progress": progress}

        return {"reply": f"Deep-dive on '{topic}' complete.", "reconciliation": text, "progress": progress}

    # ----------------- Edit section -----------------
    def edit_section(self, session_id, section, new_content):
        session_id = session_id or "anon"
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found. Generate a plan first."}

        plan = session.get("plan", {})
        # allow editing nested keys using dot notation
        if "." in section:
            top, sub = section.split(".", 1)
            if top in plan and isinstance(plan[top], dict):
                plan[top][sub] = new_content
            else:
                return {"error": "Section not recognized."}
        else:
            # top-level replacement; attempt to parse JSON for lists/objects
            if section in plan and not isinstance(plan[section], list) and not isinstance(plan[section], dict):
                plan[section] = new_content
            else:
                try:
                    parsed_content = json.loads(new_content)
                    plan[section] = parsed_content
                except Exception:
                    plan[section] = new_content

        # Ask LLM to re-summarize updated plan
        re_prompt = (
            "User edited the account plan. Update and re-summarize the entire account plan to keep it consistent.\n\n"
            "Current plan (JSON):\n" + json.dumps(plan) + "\n\n"
            "Schema:\n" + ACCOUNT_PLAN_SCHEMA + "\n\n"
            "Produce valid JSON following the schema."
        )

        try:
            response = self.safe_llm_call(
                messages=[
                    {"role":"system","content":"You are ResearchGPT; produce a corrected plan JSON."},
                    {"role":"user","content":re_prompt}
                ],
                max_tokens=1000
            )

            if response is None:
                return {"reply": "⚠️ AI temporarily overloaded. Please try again.", "account_plan": plan}

            text = response.choices[0].message.content

        except Exception as e:
            return {"reply":"Failed to re-summarize plan.", "error": str(e)}

        try:
            updated_plan = json.loads(text)
        except Exception:
            updated_plan = {"raw_output": text}

        # save back to session
        self.sessions[session_id]["plan"] = updated_plan
        return {"reply":"Section updated and plan re-summarized.", "account_plan": updated_plan}
