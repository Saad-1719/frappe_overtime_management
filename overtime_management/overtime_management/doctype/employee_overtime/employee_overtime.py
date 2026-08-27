import frappe
from frappe.model.document import Document
from frappe.utils import flt, get_first_day, get_last_day, getdate

class EmployeeOvertime(Document):
    def validate(self):
        self.calculate_ot_hours()
        self.fetch_base_salary()
        self.calculate_hourly_rate()
        self.calculate_ot_amount()

    def calculate_ot_hours(self):
        self.ot_hours = sum(flt(d.hours) for d in self.overtime_details)

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


@frappe.whitelist()
def fetch_overtime_from_timesheets(employee, period_date):
    """Pull all is_overtime=1 timesheet rows for this employee within the period_date's month."""
    start_date = get_first_day(period_date)
    end_date = get_last_day(period_date)

    timesheets = frappe.get_all(
        "Timesheet",
        filters={
            "employee": employee,
            "start_date": [">=", start_date],
            "end_date": ["<=", end_date],
            "docstatus": 1
        },
        pluck="name"
    )

    if not timesheets:
        return []

    ot_rows = frappe.get_all(
        "Timesheet Detail",
        filters={
            "parent": ["in", timesheets],
            "custom_is_overtime": 1
        },
        fields=["parent as timesheet", "from_time", "activity_type", "hours"]
    )

    details = []
    for row in ot_rows:
        details.append({
            "timesheet": row.timesheet,
            "date": getdate(row.from_time) if row.from_time else None,
            "activity_type": row.activity_type,
            "hours": row.hours
        })
    return details