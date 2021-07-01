// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Document Approver', {
        refresh: function(frm) {
        cur_frm.set_query("parent_cc", function() {
        return {
            "filters": {
                "is_group": 1
                        }
               };
                });
	},
        get_all_branch: function(frm) {
                return frappe.call({
                        method: "get_all_branches",
                        doc: frm.doc,
                        callback: function(r, rt) {
                                frm.refresh_field("items");
                                frm.refresh_fields();
                        }
                });
        }
});
