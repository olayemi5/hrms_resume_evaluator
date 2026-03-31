import frappe

PREFIX = "[CV Evaluator]"


def _file_logger():
    return frappe.logger("cv_evaluator", allow_site=True)


def info(msg):
    line = f"{PREFIX} {msg}"
    print(line)
    _file_logger().info(msg)


def warning(msg):
    line = f"{PREFIX} WARNING: {msg}"
    print(line)
    _file_logger().warning(msg)


def error(msg):
    line = f"{PREFIX} ERROR: {msg}"
    print(line)
    _file_logger().error(msg)
