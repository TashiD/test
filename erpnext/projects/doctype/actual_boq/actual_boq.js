// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Actual BOQ', {
	setup: function(frm){
        frm.get_docfield("boq_item").allow_bulk_edit = 1;

                frm.get_field('boq_item').grid.editable_fields = [
                        {fieldname: 'boq_code', columns: 1},
                        {fieldname: 'item', columns: 3},
                        {fieldname: 'is_group', columns: 1},
                        {fieldname: 'uom', columns: 1},
                        {fieldname: 'quantity', columns: 1},
                        {fieldname: 'rate', columns: 1},
                        {fieldname: 'amount', columns: 2}
                ];
        },

});

frappe.ui.form.on("Actual BOQ Item",{
        rate: function(frm, cdt, cdn){
        child = locals[cdt][cdn];
        amount = parseFloat(child.quantity)*parseFloat(child.rate)
        frappe.model.set_value(cdt, cdn, 'amount', parseFloat(amount));
        },

})

