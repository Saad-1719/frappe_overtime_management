frappe.ui.form.on("Overtime Entry", {
    refresh: function(frm) {
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button("Get Employees", function() {
                if (!frm.doc.company || !frm.doc.start_date || !frm.doc.end_date) {
                    frappe.msgprint("Please select Company, Start Date, and End Date first");
                    return;
                }

                frappe.call({
                    method: "overtime_management.overtime_management.doctype.overtime_entry.overtime_entry.get_matching_employees",
                    args: {
                        company: frm.doc.company,
                        department: frm.doc.department,
                        start_date: frm.doc.start_date,
                        end_date: frm.doc.end_date
                    },
                    callback: function(r) {
                        frm.clear_table("employees");
                        (r.message || []).forEach(row => frm.add_child("employees", row));
                        frm.refresh_field("employees");
                        frappe.msgprint(`Found ${(r.message || []).length} employee(s) with unclaimed overtime`);
                    }
                });
            });
        }

        // Only relevant after submit, once draft/submitted Employee Overtime records may exist
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button("View Generated Records", function() {
                frappe.call({
                    method: "overtime_management.overtime_management.doctype.overtime_entry.overtime_entry.get_generated_records",
                    args: {
                        overtime_entry: frm.doc.name
                    },
                    callback: function(r) {
                        const records = r.message || [];

                        if (!records.length) {
                            frappe.msgprint("No Employee Overtime records found for this entry.");
                            return;
                        }

                        const status_label = {0: "Draft", 1: "Submitted", 2: "Cancelled"};

                        const rows = records.map(rec => `
                            <tr>
                                <td>${rec.employee_name || rec.employee}</td>
                                <td><a href="/app/employee-overtime/${rec.name}" target="_blank">${rec.name}</a></td>
                                <td>${status_label[rec.docstatus]}</td>
                                <td>${format_currency(rec.ot_amount)}</td>
                            </tr>
                        `).join("");

                        const html = `
                            <table class="table table-bordered">
                                <thead>
                                    <tr>
                                        <th>Employee</th>
                                        <th>Employee Overtime</th>
                                        <th>Status</th>
                                        <th>OT Amount</th>
                                    </tr>
                                </thead>
                                <tbody>${rows}</tbody>
                            </table>
                        `;

                        frappe.msgprint({
                            title: "Generated Employee Overtime Records",
                            message: html,
                            wide: true
                        });
                    }
                });
            });
        }
    }
});