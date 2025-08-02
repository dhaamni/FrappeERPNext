// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Account Category", {
	refresh(frm) {
		if (frm.doc.is_system_generated) {
			frm.disable_form();
		}
	},
});
