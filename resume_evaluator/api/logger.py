import frappe

PREFIX = "[CV Evaluator]"


def _file_logger():
    return frappe.logger("cv_evaluator", allow_site=True)


def _safe_print(line):
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", errors="replace").decode("ascii"))


def info(msg):
    _safe_print(f"{PREFIX} {msg}")
    _file_logger().info(msg)


def warning(msg):
    _safe_print(f"{PREFIX} WARNING: {msg}")
    _file_logger().warning(msg)


def error(msg):
    _safe_print(f"{PREFIX} ERROR: {msg}")
    _file_logger().error(msg)
