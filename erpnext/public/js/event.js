// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
frappe.provide("frappe.desk");

frappe.ui.form.on("Event", {
	refresh: function (frm) {
		frm.set_query("reference_doctype", "event_participants", function () {
			return {
				filters: {
					name: ["in", ["Contact", "Lead", "Customer", "Supplier", "Employee", "Sales Partner"]],
				},
			};
		});

		// Custom query for Employee selection to bypass user permissions
		frm.set_query("reference_docname", "event_participants", function () {
			let reference_doctype = frm.get_selected_value("reference_doctype");
			if (reference_doctype === "Employee") {
				return {
					query: "erpnext.setup.doctype.employee.employee.get_employees_for_event_participants",
					filters: {},
				};
			}
		});

		frm.add_custom_button(
			__("Add Leads"),
			function () {
				new frappe.desk.eventParticipants(frm, "Lead");
			},
			__("Add Participants")
		);

		frm.add_custom_button(
			__("Add Customers"),
			function () {
				new frappe.desk.eventParticipants(frm, "Customer");
			},
			__("Add Participants")
		);

		frm.add_custom_button(
			__("Add Suppliers"),
			function () {
				new frappe.desk.eventParticipants(frm, "Supplier");
			},
			__("Add Participants")
		);

		frm.add_custom_button(
			__("Add Employees"),
			function () {
				// Custom employee selection that bypasses permissions
				frm.trigger("add_employees_as_participants");
			},
			__("Add Participants")
		);

		frm.add_custom_button(
			__("Add Sales Partners"),
			function () {
				new frappe.desk.eventParticipants(frm, "Sales Partner");
			},
			__("Add Participants")
		);
	},

	add_employees_as_participants: function (frm) {
		// Custom method to add employees as participants
		frappe.call({
			method: "erpnext.setup.doctype.employee.employee.get_employees_for_event_participants",
			args: {
				doctype: "Employee",
				txt: "",
				searchfield: "name",
				start: 0,
				page_len: 50,
				filters: {},
			},
			callback: function (r) {
				if (r.message) {
					let options = r.message.map(function (emp) {
						return {
							label: emp[1],
							value: emp[0],
						};
					});

					frappe.prompt(
						{
							fieldtype: "Select",
							label: __("Select Employee"),
							fieldname: "employee",
							options: options,
							reqd: 1,
						},
						function (data) {
							if (data.employee) {
								frm.add_child("event_participants", {
									reference_doctype: "Employee",
									reference_docname: data.employee,
								});
								frm.refresh_field("event_participants");
							}
						},
						__("Add Employee"),
						__("Add")
					);
				}
			},
		});
	},
});
