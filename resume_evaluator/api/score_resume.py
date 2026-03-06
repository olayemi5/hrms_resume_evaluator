import frappe
import json


# ─────────────────────────────────────────────
# Prompt Builder
# ─────────────────────────────────────────────

def build_prompt(resume_text, job_description):
    return f"""
Compare this resume with the job description and return ONLY valid JSON with no extra text:
{{"score": <integer 0-100>, "summary": "<short summary text>"}}.

Job Description:
{job_description}

Resume:
{resume_text}
"""


def parse_ai_response(content):
    """Parse JSON from AI response, stripping markdown fences if present."""
    content = content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    data = json.loads(content)
    return data


# ─────────────────────────────────────────────
# Provider-specific scoring
# ─────────────────────────────────────────────

def _score_with_openai(client, model, prompt):
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def _score_with_gemini(client, model, prompt):
    response = client.generate_content(prompt)
    return response.text


# ─────────────────────────────────────────────
# Main Scorer
# ─────────────────────────────────────────────

def score_resume_text(client, provider, model, resume_text, job_description):
    """
    Score a resume against a job description using the configured AI provider.
    Returns (score: int, summary: str).
    """
    # Load settings for configurable values
    try:
        name = frappe.db.get_value("Cv Evaluator Settings", {}, "name")
        settings = frappe.get_doc("Cv Evaluator Settings", name)
        summary_max_length = int(settings.summary_max_length or 1000)
        min_score = int(settings.min_score_threshold or 0)
    except Exception:
        summary_max_length = 1000
        min_score = 0

    prompt = build_prompt(resume_text, job_description)

    try:
        if provider == "OpenAI":
            raw = _score_with_openai(client, model, prompt)
        elif provider == "Gemini":
            raw = _score_with_gemini(client, model, prompt)
        else:
            raise ValueError(f"Unknown provider: {provider}")

        data = parse_ai_response(raw)
        score = int(data.get("score", 0))
        summary = data.get("summary", "")[:summary_max_length]

        if score < min_score:
            print(f"[CV Evaluator] ⚠ Score {score} is below threshold {min_score}")

    except Exception as e:
        score = 0
        summary = str(e)[:200]
        frappe.log_error(
            f"Failed to score resume: {e}", "Resume AI Scoring"
        )

    return score, summary
