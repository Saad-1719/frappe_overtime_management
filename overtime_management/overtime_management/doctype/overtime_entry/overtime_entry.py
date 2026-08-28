# import frappe
# from frappe.model.document import Document
# from frappe.utils import flt, getdate, add_days,cint


# class OvertimeEntry(Document):
#     def on_submit(self):
#         if not self.employees:
#             frappe.throw("No employees found. Click 'Get Employees' before submitting.")
#         self.create_draft_overtime_records()

#     def create_draft_overtime_records(self):
#         created, skipped = [], []

#         for row in self.employees:
#             # skip if an overlapping submitted Employee Overtime already exists
#             overlapping = frappe.db.sql("""
#                 SELECT name FROM `tabEmployee Overtime`
#                 WHERE employee = %(employee)s
#                     AND docstatus = 1
#                     AND start_date <= %(end_date)s
#                     AND end_date >= %(start_date)s
#             """, {
#                 "employee": row.employee,
#                 "start_date": self.start_date,
#                 "end_date": self.end_date
#             }, as_dict=True)

#             if overlapping:
#                 skipped.append(row.employee)
#                 continue

#             eo = frappe.new_doc("Employee Overtime")
#             eo.employee = row.employee
#             eo.start_date = self.start_date
#             eo.end_date = self.end_date
#             eo.overtime_entry = self.name

#             from overtime_management.overtime_management.doctype.employee_overtime.employee_overtime import (
#                 fetch_overtime_from_timesheets,
#             )
#             details = fetch_overtime_from_timesheets(row.employee, self.start_date, self.end_date)
#             for d in details:
#                 eo.append("overtime_details", d)

#             eo.insert()  # stays as Draft — human review/submit happens separately
#             row.employee_overtime = eo.name
#             frappe.db.set_value(row.doctype, row.name, "employee_overtime", eo.name)
#             created.append(eo.name)

#         frappe.msgprint(
#             f"Created {len(created)} draft Employee Overtime record(s). "
#             f"Skipped {len(skipped)} (already covered by an existing submitted record)."
#         )


# # @frappe.whitelist()
# # def get_matching_employees(company, department, start_date, end_date):
# #     start_date = getdate(start_date)
# #     end_date = getdate(end_date)
# #     end_datetime = f"{add_days(end_date, 1)} 00:00:00"
# #     start_datetime = f"{start_date} 00:00:00"

# #     filters = {"company": company}
# #     if department:
# #         filters["department"] = department

# #     conditions = ""
# #     values = {"start_datetime": start_datetime, "end_datetime": end_datetime}
# #     if company:
# #         conditions += " AND e.company = %(company)s"
# #         values["company"] = company
# #     if department:
# #         conditions += " AND e.department = %(department)s"
# #         values["department"] = department

# #     rows = frappe.db.sql(f"""
# #         SELECT
# #             e.name AS employee,
# #             e.employee_name,
# #             SUM(td.hours) AS ot_hours_found
# #         FROM `tabEmployee` e
# #         INNER JOIN `tabTimesheet` ts ON ts.employee = e.name
# #         INNER JOIN `tabTimesheet Detail` td ON td.parent = ts.name
# #         WHERE
# #             e.status = 'Active'
# #             AND ts.docstatus = 1
# #             AND td.custom_is_overtime = 1
# #             AND td.from_time >= %(start_datetime)s
# #             AND td.from_time < %(end_datetime)s
# #             {conditions}
# #         GROUP BY e.name
# #         ORDER BY e.employee_name
# #     """, values, as_dict=True)

# #     return rows


# @frappe.whitelist()
# def get_matching_employees(company, department, start_date, end_date):
#     start_date = getdate(start_date)
#     end_date = getdate(end_date)

#     settings = frappe.get_single("Overtime Settings")
#     lookback = cint(settings.lookback_days) or 30
#     search_start = add_days(start_date, -lookback)

#     start_datetime = f"{search_start} 00:00:00"
#     end_datetime = f"{add_days(end_date, 1)} 00:00:00"

#     conditions = ""
#     values = {"start_datetime": start_datetime, "end_datetime": end_datetime}
#     if company:
#         conditions += " AND e.company = %(company)s"
#         values["company"] = company
#     if department:
#         conditions += " AND e.department = %(department)s"
#         values["department"] = department

#     rows = frappe.db.sql(f"""
#         SELECT
#             e.name AS employee,
#             e.employee_name,
#             SUM(td.hours) AS ot_hours_found
#         FROM `tabEmployee` e
#         INNER JOIN `tabTimesheet` ts ON ts.employee = e.name
#         INNER JOIN `tabTimesheet Detail` td ON td.parent = ts.name
#         WHERE
#             e.status = 'Active'
#             AND ts.docstatus = 1
#             AND td.custom_is_overtime = 1
#             AND td.from_time >= %(start_datetime)s
#             AND td.from_time < %(end_datetime)s
#             AND td.name NOT IN (
#                 SELECT eod.timesheet_detail
#                 FROM `tabEmployee Overtime Detail` eod
#                 INNER JOIN `tabEmployee Overtime` eo ON eo.name = eod.parent
#                 WHERE eo.docstatus != 2
#                     AND eod.timesheet_detail IS NOT NULL
#                     AND eod.timesheet_detail != ''
#             )
#             {conditions}
#         GROUP BY e.name
#         ORDER BY e.employee_name
#     """, values, as_dict=True)

#     return rows


import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate, add_days, cint


class OvertimeEntry(Document):
    def on_submit(self):
        if not self.employees:
            frappe.throw("No employees found. Click 'Get Employees' before submitting.")
        self.create_draft_overtime_records()

    def create_draft_overtime_records(self):
        created, skipped = [], []

        for row in self.employees:
            # skip if an overlapping submitted Employee Overtime already exists
            overlapping = frappe.db.sql("""
                SELECT name FROM `tabEmployee Overtime`
                WHERE employee = %(employee)s
                    AND docstatus = 1
                    AND start_date <= %(end_date)s
                    AND end_date >= %(start_date)s
            """, {
                "employee": row.employee,
                "start_date": self.start_date,
                "end_date": self.end_date
            }, as_dict=True)

            if overlapping:
                skipped.append(row.employee)
                continue

            eo = frappe.new_doc("Employee Overtime")
            eo.employee = row.employee
            eo.start_date = self.start_date
            eo.end_date = self.end_date
            eo.overtime_entry = self.name

            from overtime_management.overtime_management.doctype.employee_overtime.employee_overtime import (
                fetch_overtime_from_timesheets,
            )
            details = fetch_overtime_from_timesheets(row.employee, self.start_date, self.end_date)
            for d in details:
                eo.append("overtime_details", d)

            eo.insert()  # stays as Draft — human review/submit happens separately
            created.append(eo.name)

        frappe.msgprint(
            f"Created {len(created)} draft Employee Overtime record(s). "
            f"Skipped {len(skipped)} (already covered by an existing submitted record)."
        )


@frappe.whitelist()
def get_matching_employees(company, department, start_date, end_date):
    start_date = getdate(start_date)
    end_date = getdate(end_date)

    settings = frappe.get_single("Overtime Settings")
    lookback = cint(settings.lookback_days) or 30
    search_start = add_days(start_date, -lookback)

    start_datetime = f"{search_start} 00:00:00"
    end_datetime = f"{add_days(end_date, 1)} 00:00:00"

    conditions = ""
    values = {"start_datetime": start_datetime, "end_datetime": end_datetime}
    if company:
        conditions += " AND e.company = %(company)s"
        values["company"] = company
    if department:
        conditions += " AND e.department = %(department)s"
        values["department"] = department

    rows = frappe.db.sql(f"""
        SELECT
            e.name AS employee,
            e.employee_name,
            SUM(td.hours) AS ot_hours_found
        FROM `tabEmployee` e
        INNER JOIN `tabTimesheet` ts ON ts.employee = e.name
        INNER JOIN `tabTimesheet Detail` td ON td.parent = ts.name
        WHERE
            e.status = 'Active'
            AND ts.docstatus = 1
            AND td.custom_is_overtime = 1
            AND td.from_time >= %(start_datetime)s
            AND td.from_time < %(end_datetime)s
            AND td.name NOT IN (
                SELECT eod.timesheet_detail
                FROM `tabEmployee Overtime Detail` eod
                INNER JOIN `tabEmployee Overtime` eo ON eo.name = eod.parent
                WHERE eo.docstatus != 2
                    AND eod.timesheet_detail IS NOT NULL
                    AND eod.timesheet_detail != ''
            )
            {conditions}
        GROUP BY e.name
        ORDER BY e.employee_name
    """, values, as_dict=True)

    return rows


@frappe.whitelist()
def get_generated_records(overtime_entry):
    """Live lookup replacing the old stored employee_overtime back-link.
    Returns {employee: employee_overtime_name} for every Employee Overtime
    that was generated from this Overtime Entry (any status, including cancelled)."""
    rows = frappe.db.get_all(
        "Employee Overtime",
        filters={"overtime_entry": overtime_entry},
        fields=["name", "employee", "employee_name", "docstatus", "ot_amount"]
    )
    return rows