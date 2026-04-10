import frappe
from resume_evaluator.api.fields import ensure_settings_doctype, ensure_custom_fields


def after_install():
    """Auto-setup on app install: create settings doctype, custom fields, and permissions."""
    ensure_settings_doctype()
    ensure_custom_fields()
    ensure_permlevel_access()
    frappe.db.commit()


def ensure_permlevel_access():
    """Grant permlevel 1 read on Job Applicant to HR Manager and System Manager.

    This ensures only these desk roles can see the CV evaluation fields.
    Website User (permlevel 0 only) will never see them.
    """
    for role in ("HR Manager", "System Manager", "HR User"):
        # Skip if role doesn't have permlevel 0 on Job Applicant (Frappe requirement)
        has_level_zero = frappe.db.sql("""
            SELECT name FROM `tabDocPerm`
            WHERE parent = 'Job Applicant' AND role = %s AND permlevel = 0
        """, (role,))
        if not has_level_zero:
            continue

        # Check if permlevel 1 already exists
        has_level_one = frappe.db.sql("""
            SELECT name FROM `tabDocPerm`
            WHERE parent = 'Job Applicant' AND role = %s AND permlevel = 1
        """, (role,))
        if has_level_one:
            continue

        # Insert directly to avoid DocType validate triggering unrelated errors
        frappe.db.sql("""
            INSERT INTO `tabDocPerm`
            (name, parent, parenttype, parentfield, role, permlevel, `read`, `write`)
            VALUES (%s, 'Job Applicant', 'DocType', 'permissions', %s, 1, 1, 0)
        """, (frappe.generate_hash(length=10), role))

    frappe.db.commit()
