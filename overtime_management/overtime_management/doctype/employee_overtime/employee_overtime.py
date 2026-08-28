import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate, add_days

class EmployeeOvertime(Document):
    def validate(self):
        self.calculate_ot_hours()
        self.fetch_base_salary()
        self.calculate_hourly_rate()
        self.calculate_ot_amount()

    def calculate_ot_hours(self):
        self.ot_hours = sum(flt(d.approved_hours) for d in self.overtime_details)

    def fetch_base_salary(self):
        base = frappe.db.get_value(
            "Salary Structure Assignment",
            {"employee": self.employee, "docstatus": 1},
            "base",
            order_by="from_date desc"
        )
        if not base:
            frappe.throw(f"No active Salary Structure Assignment found for {self.employee}")
        self.base_salary = flt(base)

    def calculate_hourly_rate(self):
        settings = frappe.get_single("Overtime Settings")
        monthly_hours = flt(settings.working_days_per_month) * flt(settings.working_hours_per_day)
        if monthly_hours <= 0:
            frappe.throw("Please configure Working Days/Hours in Overtime Settings")
        base_hourly_rate = self.base_salary / monthly_hours
        self.hourly_rate = base_hourly_rate * flt(settings.ot_multiplier)

    def calculate_ot_amount(self):
        self.ot_amount = flt(self.hourly_rate) * flt(self.ot_hours)

    def on_submit(self):
        self.create_additional_salary()

    def create_additional_salary(self):
        existing = frappe.db.exists(
            "Additional Salary",
            {"ref_docname": self.name, "docstatus": ["!=", 2]}
        )
        if existing:
            frappe.msgprint(f"Additional Salary {existing} already linked to this record.")
            return

        if flt(self.ot_amount) <= 0:
            frappe.msgprint("OT Amount is zero — skipping Additional Salary creation.")
            return

        add_salary = frappe.new_doc("Additional Salary")
        add_salary.employee = self.employee
        add_salary.salary_component = "Overtime"
        add_salary.amount = self.ot_amount
        add_salary.payroll_date = self.end_date
        add_salary.overwrite_salary_structure_amount = 0
        add_salary.ref_doctype = "Employee Overtime"
        add_salary.ref_docname = self.name
        add_salary.insert()
        add_salary.submit()

        frappe.msgprint(f"Additional Salary {add_salary.name} created for {self.employee}")

    def on_cancel(self):
        self.cancel_additional_salary()

    def cancel_additional_salary(self):
        existing = frappe.db.get_value(
            "Additional Salary",
            {"ref_docname": self.name, "docstatus": 1},
            "name"
        )
        if existing:
            add_salary = frappe.get_doc("Additional Salary", existing)
            add_salary.cancel()
            frappe.msgprint(f"Cancelled linked Additional Salary {existing}")


@frappe.whitelist()
def fetch_overtime_from_timesheets(employee, start_date, end_date):

    start_date = getdate(start_date)
    end_date = getdate(end_date)

    if start_date > end_date:
        frappe.throw("Start Date cannot be after End Date")

    start_datetime = f"{start_date} 00:00:00"
    end_datetime = f"{add_days(end_date, 1)} 00:00:00"

    ot_rows = frappe.db.sql("""
        SELECT
            td.parent AS timesheet,
            td.from_time,
            td.activity_type,
            td.hours
        FROM `tabTimesheet Detail` td
        INNER JOIN `tabTimesheet` ts
            ON ts.name = td.parent
        WHERE
            ts.employee = %(employee)s
            AND ts.docstatus = 1
            AND td.custom_is_overtime = 1
            AND td.from_time >= %(start_datetime)s
            AND td.from_time < %(end_datetime)s
        ORDER BY td.from_time ASC
    """, {
        "employee": employee,
        "start_datetime": start_datetime,
        "end_datetime": end_datetime
    }, as_dict=True)

    details = []

    for row in ot_rows:
        details.append({
            "timesheet": row.timesheet,
            "date": getdate(row.from_time) if row.from_time else None,
            "activity_type": row.activity_type,
            "hours": row.hours,
            "approved_hours": row.hours
        })

    return details