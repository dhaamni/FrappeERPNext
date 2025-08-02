// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Financial Report Template", {
	refresh(frm) {
		if (frm.doc.is_standard) {
			frm.dashboard.add_comment(
				__(
					"<strong>Warning:</strong> This template is system generated and may be overwritten by a future update. Duplicate it to customize."
				),
				"yellow",
				true
			);
		}
	},
});
