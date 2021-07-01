// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Issue List', {
	refresh: function(frm) {
                if(frm.doc.docstatus == 1) {
                        cur_frm.add_custom_button(__('Issue Report'), function() {
                                frappe.route_options = {
                                        name: frm.doc.name
                                };
                                frappe.set_route("query-report", "Issue Report");
                        }, __("View"));
                }

        },
});
