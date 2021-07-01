frappe.pages['barcode'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Test',
		single_column: true
	});
                frappe.call({
                        method: "erpnext.projects.doctype.project.project.testing",
                        args: {
                                from_date: 'Tashi',
                                to_date: 'Dorji'
                        },
                        callback: function(r) {
					
                        }
                });
}
