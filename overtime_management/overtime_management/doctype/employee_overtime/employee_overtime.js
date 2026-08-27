frappe.ui.form.on("Employee Overtime", {
    refresh: function(frm) {
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button("Fetch Overtime Hours", function() {
                if (!frm.doc.employee || !frm.doc.period_date) {
                    frappe.msgprint("Please select Employee and Period first");
                    return;
                }

                frappe.call({
                    method: "overtime_management.overtime_management.doctype.employee_overtime.employee_overtime.fetch_overtime_from_timesheets",
                    args: {
                        employee: frm.doc.employee,
                        period_date: frm.doc.period_date
                    },
                    callback: function(r) {
                        frm.clear_table("overtime_details");
                        (r.message || []).forEach(row => frm.add_child("overtime_details", row));
                        frm.refresh_field("overtime_details");
                        frappe.msgprint(`Fetched ${(r.message || []).length} overtime entries`);
                    }
                });
            });
        }
    }
});