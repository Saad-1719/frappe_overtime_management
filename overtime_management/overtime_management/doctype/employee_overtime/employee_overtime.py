import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate, add_days,cint

class EmployeeOvertime(Document):
    def validate(self):
        self.validate_overtime_details()
        self.calculate_ot_hours()
        self.fetch_base_salary()
        self.calculate_hourly_rate()
        self.calculate_ot_amount()

    def validate_overtime_details(self):
        if not self.overtime_details:
            frappe.throw("Cannot save: no overtime entries found. Click 'Fetch Overtime Hours' first.")
    
    def calculate_ot_hours(self):
        self.ot_hours = sum(flt(d.approved_hours) for d in self.overtime_details)

    def fetch_base_salary(self):
        settings = frappe.get_single("Overtime Settings")
        component = settings.salary_component
        if not component:
            frappe.throw("Please configure an OT Basis Salary Component in Overtime Settings")

        # 1. Try latest submitted Salary Slip first (most accurate — real computed value)
        row = frappe.db.sql("""
            SELECT sd.amount
            FROM `tabSalary Detail` sd
            INNER JOIN `tabSalary Slip` ss ON ss.name = sd.parent
            WHERE ss.employee = %(employee)s
                AND ss.docstatus = 1
                AND sd.parentfield = 'earnings'
                AND sd.salary_component = %(component)s
            ORDER BY ss.end_date DESC
            LIMIT 1
        """, {"employee": self.employee, "component": component}, as_dict=True)

        if row:
            self.base_salary = flt(row[0].amount)
            return

        # 2. Fallback: no payroll history yet — inspect the assigned Salary Structure
        ssa = frappe.db.get_value(
            "Salary Structure Assignment",
            {"employee": self.employee, "docstatus": 1},
            ["name", "salary_structure", "base"],
            order_by="from_date desc",
            as_dict=True
        )
        if not ssa:
            frappe.throw(
                f"No submitted Salary Slip and no Salary Structure Assignment found for {self.employee}. "
                f"Cannot calculate overtime."
            )

        detail = frappe.db.get_value(
            "Salary Detail",
            {"parent": ssa.salary_structure, "parentfield": "earnings", "salary_component": component},
            ["amount", "formula"],
            as_dict=True
        )
        if not detail:
            frappe.throw(
                f"Salary Structure '{ssa.salary_structure}' assigned to {self.employee} has no "
                f"component '{component}'. Please check Overtime Settings or the employee's Salary Structure."
            )

        if not detail.formula and flt(detail.amount) > 0:
            # flat-amount component
            self.base_salary = flt(detail.amount)
        elif (detail.formula or "").strip() == "base":
            # standard ERPNext pattern: component = base salary directly
            self.base_salary = flt(ssa.base)
        else:
            frappe.throw(
                f"'{component}' is calculated using a custom formula ('{detail.formula}') on Salary Structure "
                f"'{ssa.salary_structure}', and no Salary Slip exists yet to read its computed value from. "
                f"Overtime cannot be calculated for {self.employee} until their first Salary Slip is submitted."
            )

        frappe.msgprint(
            f"No Salary Slip found yet for {self.employee}. Using {component} = {self.base_salary} "
            f"from Salary Structure Assignment — this is an estimate until the first payroll run.",
            indicator="orange"
        )
    
    def calculate_hourly_rate(self):
        settings = frappe.get_single("Overtime Settings")
        monthly_hours = flt(settings.standard_working_hours_per_month)
        if monthly_hours <= 0:
            frappe.throw("Please configure Standard Working Hours Per Month in Overtime Settings")
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

    settings = frappe.get_single("Overtime Settings")
    lookback = cint(settings.lookback_days) or 30

    search_start = add_days(start_date, -lookback)
    start_datetime = f"{search_start} 00:00:00"
    end_datetime = f"{add_days(end_date, 1)} 00:00:00"

    ot_rows = frappe.db.sql("""
        SELECT
            td.name AS timesheet_detail,
            td.parent AS timesheet,
            td.from_time,
            td.activity_type,
            td.hours,
            td.project, 
            td.task
        FROM `tabTimesheet Detail` td
        INNER JOIN `tabTimesheet` ts
            ON ts.name = td.parent
        WHERE
            ts.employee = %(employee)s
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
        ORDER BY td.from_time ASC
    """, {
        "employee": employee,
        "start_datetime": start_datetime,
        "end_datetime": end_datetime
    }, as_dict=True)

    details = []

    for row in ot_rows:
        details.append({
            "timesheet_detail": row.timesheet_detail,
            "timesheet": row.timesheet,
            "date": getdate(row.from_time) if row.from_time else None,
            "activity_type": row.activity_type,
            "hours": row.hours,
            "approved_hours": row.hours,
            "is_prior_period": 1 if getdate(row.from_time) < start_date else 0

        })

    return details