import frappe
from frappe.utils import strip_html
from resume_evaluator.api.fields import ensure_custom_fields, ensure_settings_doctype
from resume_evaluator.api.ai_clients import get_ai_client
from resume_evaluator.api.extractors import get_resume_text
from resume_evaluator.api.score_resume import score_resume_text
from resume_evaluator.api.logger import info, warning, error


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
    info("── Scheduler run started ──")

    ensure_settings_doctype()
    ensure_custom_fields()

    client, provider, model = get_ai_client()
    if client is None:
        warning("Aborting — AI client not initialized. Check Cv Evaluator Settings.")
        return

    applicants = get_unprocessed_applicants()
    if not applicants:
        info("No unevaluated applicants found. Nothing to do.")
        return

    total = len(applicants)
    processed = 0
    skipped = 0
    failed = 0

    info(f"Found {total} unevaluated applicant(s). Starting processing...")

    for a in applicants:
        applicant_name = a["name"]
        full_name = a.get("applicant_name") or ""
        job_opening_name = a.get("job_title")

        if not job_opening_name:
            warning(f"SKIP {applicant_name} ({full_name}) — no Job Opening linked.")
            frappe.log_error(f"No job opening linked for {applicant_name}", "Resume Processing")
            skipped += 1
            continue

        raw_desc = frappe.get_value("Job Opening", job_opening_name, "description") or ""
        job_desc = strip_html(raw_desc)

        if not job_desc.strip():
            warning(f"SKIP {applicant_name} ({full_name}) — Job Opening '{job_opening_name}' has empty description.")
            skipped += 1
            continue

        resume_text = get_resume_text(applicant_name)
        if not resume_text.strip():
            warning(f"SKIP {applicant_name} ({full_name}) — no resume file or text extracted.")
            frappe.log_error(f"No resume text found for {applicant_name}", "Resume Processing")
            skipped += 1
            continue

        try:
            info(f"Processing {applicant_name} ({full_name}) against '{job_opening_name}'...")

            result = score_resume_text(
                client, provider, model,
                resume_text, job_desc,
                applicant_name=full_name,
                applicant_email=a.get("email_id") or "",
            )
            update_applicant(applicant_name, result)

            flag = result.get("security_flag", "Clean")
            score = result.get("score", 0)

            if flag != "Clean":
                warning(f"FLAGGED {applicant_name} ({full_name}) — {flag}: {result.get('security_note', '')[:100]}")
            else:
                info(f"OK {applicant_name} ({full_name}) — score: {score}, flag: {flag}")

            processed += 1

        except Exception as e:
            failed += 1
            error(f"FAIL {applicant_name} ({full_name}) — {e}")
            frappe.log_error(
                title=f"Resume eval failed: {applicant_name}"[:140],
                message=str(e),
            )

    info(
        f"── Scheduler run complete ── "
        f"Total: {total} | Processed: {processed} | Skipped: {skipped} | Failed: {failed}"
    )
