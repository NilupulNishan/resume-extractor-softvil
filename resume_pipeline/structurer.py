"""
structurer.py
-------------
Stage 3 — GPT-4o Single-Pass Structuring

Takes raw extracted text from Document Intelligence and sends ONE GPT-4o call.
Returns two things in a single response:
  1. Structured JSON — normalized candidate data matching the Cosmos DB schema
  2. embeddingText   — a semantic summary optimized for vector search (Stage 4 input)

Why a single pass:
  - Cost efficient: one call instead of two
  - Consistent: both outputs share the same understanding of the resume
  - The embeddingText is written with full context of the entire document

Input:  raw text string (from extractor.py)
Output: dict with keys 'structuredJson' and 'embeddingText'
        → structuredJson  goes to Cosmos DB (Stage 5)
        → embeddingText   goes to embedder.py (Stage 4)
"""

import json
from datetime import date

from resume_pipeline.clients import openai_client, GPT4O_DEPLOYMENT


# ── Prompt ─────────────────────────────────────────────────────────────────────
# This is the most important piece of the pipeline.
# Changes here affect every downstream stage. Test carefully after any edit.

SYSTEM_PROMPT = """You are an expert resume parser for an Applicant Tracking System (ATS).
Your job is to extract and normalize candidate information from raw resume text into a structured JSON format.
You must return ONLY valid JSON — no markdown, no code fences, no explanation. Just the JSON object.
Be thorough. Infer reasonable values where clearly implied. Use null for genuinely missing fields."""

USER_PROMPT_TEMPLATE = """TODAY'S DATE: {today}
Use this date as the value of "Present" when calculating durations and total experience.

Parse the following resume and return a single JSON object with EXACTLY this structure.
Do not add or remove top-level keys.

{{
  "personalInfo": {{
    "fullName":    "string — candidate full name",
    "email":       "string or null",
    "phone":       "string or null",
    "location":    "string or null — city, country preferred",
    "linkedIn":    "string or null — full URL",
    "github":      "string or null — full URL",
    "portfolio":   "string or null — any other personal site URL"
  }},

  "summary": "string — candidate's own profile/summary statement, copied faithfully if present, else null",

  "workExperience": [
    {{
      "company":          "string",
      "title":            "string — job title",
      "startDate":        "string — YYYY-MM or YYYY",
      "endDate":          "string — YYYY-MM, YYYY, or 'Present'",
      "durationMonths":   "integer or null — total months in role, use TODAY for open roles",
      "location":         "string or null",
      "responsibilities": ["string"],
      "achievements":     ["string — quantified achievements if any"]
    }}
  ],

  "education": [
    {{
      "degree":      "string",
      "institution": "string",
      "startDate":   "string or null",
      "endDate":     "string or null",
      "gpa":         "string or null",
      "honors":      "string or null"
    }}
  ],

  "skills": {{
    "raw":        ["string"],
    "normalized": ["string"],
    "technical":  ["string"],
    "soft":       ["string"]
  }},

  "certifications": [
    {{
      "name":   "string",
      "issuer": "string or null",
      "date":   "string or null",
      "proof":  "string or null — URL or credential ID"
    }}
  ],

  "projects": [
    {{
      "title":       "string",
      "description": "string",
      "techStack":   ["string"],
      "url":         "string or null"
    }}
  ],

  "languages": [
    {{
      "language":    "string",
      "proficiency": "string or null — e.g. Native, Fluent, Intermediate"
    }}
  ],

  "currentRole":          "string — most recent job title",
  "currentCompany":       "string or null — most recent company",
  "totalExperienceYears": "number — sum of all work experience durations from first job start date to TODAY ({today}), rounded to 1 decimal",

  "embeddingText": "string — see embeddingText instructions below"
}}

────────────────────────────────────────────────────────
embeddingText INSTRUCTIONS
────────────────────────────────────────────────────────
Write a fluent professional narrative optimised for semantic vector search.
Brief a hiring manager in cohesive prose — no bullet points or comma-separated lists.
Cover all of the following:

1. Professional identity and specialisation
2. Total years of experience (calculated to TODAY: {today}) and environment scale
   (startup vs enterprise)
3. Educational background — degrees, institutions, honours
4. Core competencies with how they are applied, not just tool names
   (e.g. "architects CI/CD pipelines" not "knows Jenkins")
5. Industries and calibre of employers served
6. Certifications and notable projects
7. Ideal roles and seniority levels this candidate is qualified for

────────────────────────────────────────────────────────
Resume text to parse:
---
{raw_text}
---"""


def structure_resume(raw_text: str) -> dict:
    """
    Parse raw resume text into a structured JSON + embeddingText using GPT-4o.

    Args:
        raw_text: Clean text string from Document Intelligence (extractor.py output)

    Returns:
        dict with keys:
            'structuredJson'  — full normalized candidate data (→ Cosmos DB)
            'embeddingText'   — semantic summary string (→ embedder.py / AI Search)

    Raises:
        ValueError: If GPT-4o returns invalid JSON or missing required keys
        Exception:  If the API call itself fails
    """
    #Today's date at call-time
    today_str = date.today().strftime("%B %d, %Y")

    #Use .format() — double braces {{ }} in the template collapse to { }
    prompt = USER_PROMPT_TEMPLATE.format(
        today=today_str,
        raw_text=raw_text,
    )

    response = openai_client.chat.completions.create(
        model=GPT4O_DEPLOYMENT,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        response_format={"type": "json_object"},  # Guarantees JSON output
        temperature=0.1,                           # Low temperature for consistent extraction
        max_tokens=4096,
    )

    raw_json_str = response.choices[0].message.content.strip()

    # Parse and validate
    try:
        parsed = json.loads(raw_json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"GPT-4o returned invalid JSON: {e}\nRaw output: {raw_json_str[:500]}")

    # Validate the two critical keys that flow downstream
    if "embeddingText" not in parsed:
        raise ValueError("GPT-4o output missing 'embeddingText' — check prompt and retry")

    if "personalInfo" not in parsed:
        raise ValueError("GPT-4o output missing 'personalInfo' — check prompt and retry")

    # Split into the two outputs the pipeline needs.
    # Output contract is unchanged — downstream stages (Cosmos DB, AI Search) are unaffected.
    embedding_text  = parsed.pop("embeddingText")   # → embedder.py / AI Search index
    structured_json = parsed                         # → Cosmos DB

    return {
        "structuredJson": structured_json,
        "embeddingText":  embedding_text,
    }