
from __future__ import unicode_literals
import frappe
from frappe import _

@frappe.whitelist()
def test():
	return frappe.db.sql(""" select name from `tabEmployee` where name = 'GYAL20429'""", as_dict =1)
