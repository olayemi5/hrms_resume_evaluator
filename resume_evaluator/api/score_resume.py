import frappe
from openai import OpenAI
import os
import requests
from pathlib import Path
import tempfile
from pdfplumber import open as open_pdf
from docx import Document
import json


# ─────────────────────────────────────────────
# 1.  CUSTOM FIELDS – create them if missing
# ─────────────────────────────────────────────

REQUIRED_CUSTOM_FIELDS = [
    {
        "fieldname": "custom_evaluation_done",
        "label": "Evaluation Done",
        "fieldtype": "Check",
        "default": "0",
        "insert_after": "cover_letter",
    },
    {
        "fieldname": "custom_match_score",
        "label": "Match Score",
        "fieldtype": "Int",
        "insert_after": "custom_evaluation_done",
    },
    {
        "fieldname": "custom_match_summary",
        "label": "Match Summary",
        "fieldtype": "Small Text",
        "insert_after": "custom_match_score",
    },
]


def ensure_custom_fields():
    """Create any missing custom fields on Job Applicant."""
    for field_def in REQUIRED_CUSTOM_FIELDS:
        exists = frappe.db.exists(
            "Custom Field",
            {"dt": "Job Applicant", "fieldname": field_def["fieldname"]},
        )
        if not exists:
            cf = frappe.get_doc(
                {
                    "doctype": "Custom Field",
                    "dt": "Job Applicant",
                    **field_def,
                }
            )
            cf.insert(ignore_permissions=True)
            frappe.db.commit()
            print(f"[CV Evaluator] Created custom field: {field_def['fieldname']}")
        else:
            print(f"[CV Evaluator] Field already exists: {field_def['fieldname']}")


# ─────────────────────────────────────────────
# 2.  API KEY – fetch from CV Evaluator Settings
# ─────────────────────────────────────────────

def get_openai_client():
    """
    Returns an OpenAI client using the key stored in
    'Cv Evaluator Settings' → custom_bot_key.
    Returns None (with a printed warning) if the key is not set.
    """
    try:
        from frappe.utils.password import get_decrypted_password
        api_key = get_decrypted_password("Cv Evaluator Settings", "Cv Evaluator Settings", "custom_bot_key")
    except Exception as e:
        print(f"[CV Evaluator] Could not read Cv Evaluator Settings: {e}")
        return None

    if not api_key or not api_key.strip():
        print(
            "[CV Evaluator] bot_key not set. "
            "Please configure it in Cv Evaluator Settings → custom_bot_key."
        )
        return None

    return OpenAI(api_key=api_key.strip())


# ─────────────────────────────────────────────
# 3.  CORE HELPERS
# ─────────────────────────────────────────────

def get_unprocessed_applicants():
    return frappe.get_all(
        "Job Applicant",
        filters={"custom_evaluation_done": 0},
        fields=["name", "job_title"],
    )


def download_file(file_url):
    if file_url.startswith("/"):
        return Path(frappe.get_site_path()) / file_url.lstrip("/")
    r = requests.get(file_url)
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.write(r.content)
    temp_file.close()
    return Path(temp_file.name)


def extract_text_from_file(file_path):
    text = ""
    file_path = Path(file_path)
    if file_path.suffix.lower() == ".pdf":
        with open_pdf(file_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
    elif file_path.suffix.lower() == ".docx":
        doc = Document(file_path)
        for para in doc.paragraphs:
            text += para.text + "\n"
    else:
        frappe.log_error(
            f"Unsupported file type: {file_path}", "Resume Extraction"
        )
    return text


def get_resume_text(applicant_name):
    files = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Job Applicant",
            "attached_to_name": applicant_name,
        },
        fields=["file_url"],
    )
    all_text = ""
    for f in files:
        file_path = download_file(f["file_url"])
        all_text += extract_text_from_file(file_path)

        # Delete only temp files (externally downloaded), not local Frappe files
        if not f["file_url"].startswith("/"):
            try:
                Path(file_path).unlink(missing_ok=True)
                print(f"[CV Evaluator] Removed temp file: {file_path}")
            except Exception as e:
                frappe.log_error(
                    f"Failed to remove temp file {file_path}: {e}",
                    "Resume Cleanup",
                )

    return all_text


def score_resume_text(client, resume_text, job_description):
    prompt = f"""
Compare this resume with the job description and return ONLY JSON:
{{"score": 0-100, "summary": "short summary text"}}.

Job Description:
{job_description}

Resume:
{resume_text}
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
    )
    content = response.choices[0].message.content.strip()

    # Strip markdown code fences if present
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    try:
        data = json.loads(content)
        score = int(data.get("score", 0))
        summary = data.get("summary", "")[:1000]
    except Exception as e:
        score = 0
        summary = content[:200]
        frappe.log_error(
            f"Failed to parse AI output: {e}\n{content}", "Resume AI Parsing"
        )

    return score, summary


def update_applicant(applicant_name, score, summary):
    doc = frappe.get_doc("Job Applicant", applicant_name)
    doc.custom_match_score = score
    doc.custom_match_summary = summary
    doc.custom_evaluation_done = 1
    doc.save(ignore_permissions=True)
    frappe.db.commit()


# ─────────────────────────────────────────────
# 4.  MAIN ENTRY POINT
# ─────────────────────────────────────────────

def process_all_unprocessed():
    # Step 1 – make sure the custom fields exist
    ensure_custom_fields()

    # Step 2 – get the OpenAI client (exits cleanly if key is missing)
    client = get_openai_client()
    if client is None:
        return  # message already printed; nothing crashes

    # Step 3 – process each unprocessed applicant
    applicants = get_unprocessed_applicants()
    if not applicants:
        print("[CV Evaluator] No unprocessed applicants found.")
        return

    for a in applicants:
        applicant_name = a["name"]
        job_opening_name = a["job_title"]

        job_desc = (
            frappe.get_value("Job Opening", job_opening_name, "description") or ""
        )
        resume_text = get_resume_text(applicant_name)

        if not resume_text.strip():
            frappe.log_error(
                f"No resume text found for {applicant_name}", "Resume Processing"
            )
            continue

        score, summary = score_resume_text(client, resume_text, job_desc)
        update_applicant(applicant_name, score, summary)
        print(f"[CV Evaluator] Processed {applicant_name} → score {score}")
