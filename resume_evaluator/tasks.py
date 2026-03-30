import frappe
from resume_evaluator.api.fields import ensure_custom_fields, ensure_settings_doctype
from resume_evaluator.api.ai_clients import get_ai_client
from resume_evaluator.api.extractors import get_resume_text
from resume_evaluator.api.score_resume import score_resume_text


def get_unprocessed_applicants():
    return frappe.get_all(
        "Job Applicant",
        filters={"custom_evaluation_done": 0},
        fields=["name", "job_title", "applicant_name", "email_id"],
    )


def update_applicant(applicant_name, result):
    doc = frappe.get_doc("Job Applicant", applicant_name)
    doc.custom_match_score = result["score"]
    doc.custom_match_summary = result["summary"]
    doc.custom_security_flag = result["security_flag"]
    doc.custom_security_note = result["security_note"]
    doc.custom_skills = result["skills"]
    doc.custom_education = result["education"]
    doc.custom_years_of_experience = result["years_of_experience"]
    doc.custom_previous_employments = result["previous_employments"]
    doc.custom_referees = result["referees"]
    doc.custom_other_insights = result["other_insights"]
    doc.custom_evaluation_done = 1
    doc.save(ignore_permissions=True)
    frappe.db.commit()


def process_all_unprocessed():
    """Scheduled task: evaluate all unevaluated Job Applicant resumes."""
    ensure_settings_doctype()
    ensure_custom_fields()

    client, provider, model = get_ai_client()
    if client is None:
        return

    applicants = get_unprocessed_applicants()
    if not applicants:
        return

    for a in applicants:
        applicant_name = a["name"]
        job_opening_name = a["job_title"]

        job_desc = frappe.get_value("Job Opening", job_opening_name, "description") or ""

        resume_text = get_resume_text(applicant_name)
        if not resume_text.strip():
            frappe.log_error(f"No resume text found for {applicant_name}", "Resume Processing")
            continue

        result = score_resume_text(
            client, provider, model,
            resume_text, job_desc,
            applicant_name=a.get("applicant_name") or "",
            applicant_email=a.get("email_id") or "",
        )
        update_applicant(applicant_name, result)
