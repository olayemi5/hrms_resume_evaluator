import frappe

no_cache = 1

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw("Please log in to view your applications.", frappe.PermissionError)

    context.applications = frappe.get_all(
        "Job Applicant",
        filters={"email_id": frappe.session.user},
        fields=["name", "applicant_name", "job_title", "status", "creation"],
        order_by="creation desc",
        ignore_permissions=True,
    )

    for app in context.applications:
        if app.job_title:
            app.job_title_label = (
                frappe.db.get_value("Job Opening", app.job_title, "job_title") or app.job_title
            )
        else:
            app.job_title_label = "N/A"
