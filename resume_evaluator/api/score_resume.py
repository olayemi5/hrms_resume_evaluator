import frappe
from openai import OpenAI
import os
import requests
from pathlib import Path
import tempfile
from pdfplumber import open as open_pdf
from docx import Document
import json

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def get_unprocessed_applicants():
    return frappe.get_all(
        "Job Applicant",
        filters={"custom_evaluation_done": 0},
        fields=["name", "job_title"]
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
        frappe.log_error(f"Unsupported file type: {file_path}", "Resume Extraction")
    return text

def get_resume_text(applicant_name):
    files = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Job Applicant",
            "attached_to_name": applicant_name
        },
        fields=["file_url"]
    )
    all_text = ""
    for f in files:
        file_path = download_file(f["file_url"])
        all_text += extract_text_from_file(file_path)
        # Delete temporary file after processing
        if "/private/files/" not in str(file_path):  # only delete temp files
            continue
        try:
            print(f"Removing temp file: {file_path}")
        except Exception as e:
            frappe.log_error(f"Failed to remove temp file {file_path}: {e}", "Resume Cleanup")
    return all_text

def score_resume_text(resume_text, job_description):
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
        messages=[{"role": "user", "content": prompt}]
    )

    content = response.choices[0].message.content.strip()
    # Remove markdown code block if GPT-4 wrapped JSON
    if content.startswith("```json"):
        content = content.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(content)
        score = int(data.get("score", 0))
        summary = data.get("summary", "")[:1000]
    except Exception as e:
        score = 0
        summary = content[:200]
        frappe.log_error(f"Failed to parse AI output: {e}\n{content}", "Resume AI Parsing")

    return score, summary

def update_applicant(applicant_name, score, summary):
    doc = frappe.get_doc("Job Applicant", applicant_name)
    doc.custom_match_score = score
    doc.custom_match_summary = summary
    doc.custom_evaluation_done = 1
    doc.save(ignore_permissions=True)
    frappe.db.commit()

def process_all_unprocessed():
    applicants = get_unprocessed_applicants()
    for a in applicants:
        applicant_name = a["name"]
        job_opening_name = a["job_title"]
        # Pull JD from Job Opening
        job_desc = frappe.get_value("Job Opening", job_opening_name, "description") or ""
        resume_text = get_resume_text(applicant_name)
        if not resume_text.strip():
            frappe.log_error(f"No resume text found for {applicant_name}", "Resume Processing")
            continue
        score, summary = score_resume_text(resume_text, job_desc)
        update_applicant(applicant_name, score, summary)
