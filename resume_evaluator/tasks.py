import frappe
from frappe.utils import strip_html, get_url
from jinja2 import Template
from resume_evaluator.api.fields import ensure_custom_fields, ensure_settings_doctype
from resume_evaluator.api.ai_clients import get_ai_client
from resume_evaluator.api.extractors import get_resume_text
from resume_evaluator.api.score_resume import score_resume_text
from resume_evaluator.api.logger import info, warning, error


DEFAULT_REJECTION_TEMPLATE = """
<p>Dear {{ applicant_name or 'Applicant' }},</p>
<p>Thank you for your interest in the <strong>{{ job_title }}</strong> position
and for taking the time to submit your application.</p>
<p>After careful review, we regret to inform you that we are unable to
proceed with your application at this time.</p>
<p>We encourage you to apply for future openings that match your profile.
We wish you the very best in your career.</p>
<p>Kind regards</p>
""".strip()

DEFAULT_ACCEPTANCE_TEMPLATE = """
<p>Dear {{ applicant_name or 'Applicant' }},</p>
<p>Thank you for applying for the <strong>{{ job_title }}</strong> position.
We have received your application and it is currently under review.</p>
<p>We have created a portal account for you where you can track the
status of your application(s).</p>
<p><strong>Set up your account:</strong><br>
<a href="{{ setup_link }}">{{ setup_link }}</a></p>
<p>Once your password is set, you can log in anytime to check your
application status at:<br>
<a href="{{ portal_link }}">{{ portal_link }}</a></p>
<p>We will be in touch as the review progresses.</p>
<p>Kind regards</p>
""".strip()


def _get_settings():
    """Read all relevant settings from Cv Evaluator Settings."""
    try:
        settings_name = frappe.db.get_value("Cv Evaluator Settings", {}, "name")
        values = frappe.db.get_value(
            "Cv Evaluator Settings", settings_name,
            ["rejection_email_template", "acceptance_email_template", "rejection_delay_minutes"],
            as_dict=True,
        ) or {}
    except Exception:
        values = {}

    return {
        "rejection_template": values.get("rejection_email_template") or DEFAULT_REJECTION_TEMPLATE,
        "acceptance_template": values.get("acceptance_email_template") or DEFAULT_ACCEPTANCE_TEMPLATE,
        "rejection_delay_minutes": int(values.get("rejection_delay_minutes") or 0),
    }


def _render_template(template_str, context):
    """Render a Jinja template string with the given context."""
    return Template(template_str).render(**context)


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

    try:
        settings_name = frappe.db.get_value("Cv Evaluator Settings", {}, "name")
        min_score = int(frappe.db.get_value(
            "Cv Evaluator Settings", settings_name, "min_score_threshold"
        ) or 0)
    except Exception:
        min_score = 0

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
        email = a.get("email_id") or ""
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
                applicant_email=email,
            )
            update_applicant(applicant_name, result)

            flag = result.get("security_flag", "Clean")
            score = result.get("score", 0)

            if flag != "Clean":
                warning(f"FLAGGED {applicant_name} ({full_name}) — {flag}: {result.get('security_note', '')[:100]}")
            else:
                info(f"OK {applicant_name} ({full_name}) — score: {score}, flag: {flag}")

            # Post-evaluation actions
            if email:
                _handle_post_evaluation(applicant_name, full_name, email, score, min_score, job_opening_name, flag)
            else:
                warning(f"Skipping post-eval for {applicant_name}: no email address")

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


# ─────────────────────────────────────────────
# Post-evaluation actions
# ─────────────────────────────────────────────

def _get_job_title(job_opening_name):
    """Get the human-readable job title from a Job Opening."""
    return frappe.db.get_value("Job Opening", job_opening_name, "job_title") or job_opening_name


def _handle_post_evaluation(applicant_name, full_name, email, score, min_score, job_opening_name, flag="Clean"):
    """Route to reject or accept based on threshold and security flag."""
    job_title = _get_job_title(job_opening_name)

    info(f"Post-eval: {applicant_name} score={score}, min_score={min_score}, flag={flag}")

    # Auto-reject if flagged or below threshold
    if flag != "Clean":
        info(f"Auto-rejecting {applicant_name} due to security flag: {flag}")
        _reject_applicant(applicant_name, full_name, email, job_title)
    elif min_score is not None and min_score > 0 and score < min_score:
        _reject_applicant(applicant_name, full_name, email, job_title)
    else:
        _accept_applicant(applicant_name, full_name, email, job_title)


def _reject_applicant(applicant_name, full_name, email, job_title):
    """Update status to Rejected and send/schedule rejection email."""
    try:
        doc = frappe.get_doc("Job Applicant", applicant_name)
        doc.status = "Rejected"
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        info(f"REJECTED {applicant_name} ({full_name}) — status updated to Rejected")

        settings = _get_settings()
        message = _render_template(settings["rejection_template"], {
            "applicant_name": full_name,
            "job_title": job_title,
        })
        subject = f"Application Update — {job_title}"
        delay = settings["rejection_delay_minutes"]

        if delay > 0:
            from datetime import datetime, timedelta
            execute_at = datetime.now() + timedelta(minutes=delay)
            info(f"Scheduling rejection email for {applicant_name} at {execute_at} ({delay} min delay)")
            frappe.enqueue(
                "resume_evaluator.tasks.send_delayed_email",
                queue="short",
                at_front=False,
                enqueue_after_commit=True,
                execute_at=execute_at,
                recipient=email,
                recipient_name=full_name,
                subject=subject,
                message=message,
            )
        else:
            _send_email(email, full_name, subject=subject, message=message)

    except Exception as e:
        error(f"Failed to reject {applicant_name}: {e}")
        frappe.log_error(title=f"Reject failed: {applicant_name}"[:140], message=str(e))


def _accept_applicant(applicant_name, full_name, email, job_title):
    """Send application-received email and create portal user with set-password link."""
    try:
        doc = frappe.get_doc("Job Applicant", applicant_name)
        doc.status = "Replied"
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        info(f"ACCEPTED {applicant_name} ({full_name}) — status updated to Replied")

        if not frappe.db.exists("User", email):
            user = frappe.get_doc({
                "doctype": "User",
                "email": email,
                "first_name": full_name.split()[0] if full_name else email,
                "last_name": " ".join(full_name.split()[1:]) if full_name and len(full_name.split()) > 1 else "",
                "user_type": "Website User",
                "send_welcome_email": 0,
            })
            user.insert(ignore_permissions=True)
            frappe.db.commit()
            info(f"Portal user created for {email}")
        else:
            info(f"Portal user already exists for {email}")

        # Always generate a fresh reset key so the candidate can set their password
        from frappe.utils import random_string, now_datetime
        key = random_string(32)
        frappe.db.set_value("User", email, {
            "reset_password_key": key,
            "last_reset_password_key_generated_on": now_datetime(),
        })
        frappe.db.commit()

        setup_link = get_url(f"/update-password?key={key}")
        portal_link = get_url("/my-applications")

        settings = _get_settings()
        message = _render_template(settings["acceptance_template"], {
            "applicant_name": full_name,
            "job_title": job_title,
            "setup_link": setup_link,
            "portal_link": portal_link,
        })

        _send_email(
            email, full_name,
            subject=f"Application Received — {job_title}",
            message=message,
        )

    except Exception as e:
        error(f"Failed to accept {applicant_name}: {e}")
        frappe.log_error(title=f"Accept failed: {applicant_name}"[:140], message=str(e))


def send_delayed_email(recipient, recipient_name, subject, message):
    """Background job target for delayed rejection emails."""
    _send_email(recipient, recipient_name, subject=subject, message=message)


def _send_email(recipient, recipient_name, subject, message):
    """Send email with detailed logging. Falls back to queue if now=True fails."""
    info(f"Sending email to {recipient}: {subject}")
    try:
        frappe.sendmail(
            recipients=[recipient],
            subject=subject,
            message=message,
            now=True,
        )
        info(f"Email sent successfully to {recipient}")
    except Exception as e:
        warning(f"Immediate send failed for {recipient}, queuing instead: {e}")
        try:
            frappe.sendmail(
                recipients=[recipient],
                subject=subject,
                message=message,
                now=False,
            )
            info(f"Email queued for {recipient}")
        except Exception as e2:
            error(f"Email completely failed for {recipient}: {e2}")
            frappe.log_error(title=f"Email failed: {recipient}"[:140], message=str(e2))
            raise
