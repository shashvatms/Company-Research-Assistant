ACCOUNT_PLAN_SCHEMA = """
Return ONLY a JSON object with this structure:

{
  "company_name": string,
  "snapshot": {
    "description": string,
    "headquarters": string,
    "founded": string,
    "revenue_estimate": string,
    "employees_estimate": string,
    "primary_products": [string]
  },
  "market_opportunity": {
    "segment": string,
    "tams_sams_soms": string,
    "growth_drivers": [string]
  },
  "ideal_customer_profile": {
    "industry": string,
    "company_size": string,
    "revenues": string,
    "geography": string
  },
  "key_stakeholders": [
    {"role": string, "name": string | null, "linkedin": string | null}
  ],
  "tech_stack": [string],
  "competitive_landscape": [
    {"competitor": string, "notes": string, "sources": [string]}
  ],
  "risks_and_assumptions": [string],
  "recommended_next_steps": [string],
  "sources": [
    {"url": string, "title": string, "date": string}
  ],
  "confidence": "low | medium | high"
}
"""

RAG_PROMPT = """
Your role: You research companies and create account plans.

Use ONLY the following context and user request.

CONTEXT:
{context}

USER REQUEST:
{request}

TASK:
Generate an accurate Account Plan following this schema:
{schema}

Rules:
- If sources conflict, add a field "conflicts".
- Keep the JSON clean and valid.
"""
