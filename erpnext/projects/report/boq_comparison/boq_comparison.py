# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)


	return columns, data

def get_columns():
	return [
		("Project") + ":Link/Project:100",
		("Cost Center") + ":Data:120",
		("Branch") + ":Data:120",
		("BOQ Type")+ ":Data:80",
		("BOQ Date") + ":Data:80",
		("Name") + ":Link/BOQ:110",
		("Total Amount (A)") + ":Currency:130",
                ("Market Amount (B)") + ":Currency:130",
		("Actual Amount (C")+ ":Currency:130",
		("Difference Amount (B-A) ")+ ":Currency:190",
		("Difference Amount (C-A)")+ ":Currency:190"
	]

def get_data(filters):
	query =  """
			select 
				b.project, 
				b.cost_center, 
				b.branch, 
				b.boq_type, 
				b.boq_date, 
				b.name, 
				b.total_amount,
				m.total_amount, 
				a.total_amount,
				m.total_amount - b.total_amount,
				a.total_amount - b.total_amount 
			from `tabBOQ` as b left join `tabMarket BOQ` m on m.boq = b.name
			left join  `tabActual BOQ` a on a.boq = b.name
			where b.docstatus =1
	""" 
	if filters.get("project"):
		query += ' and b.project = "{0}"'.format(str(filters.project))

	if filters.get("from_date") and filters.get("to_date"):
		query += " and b.boq_date between \'" + str(filters.from_date) + "\' and \'"+ str(filters.to_date) + "\'"
	elif filters.get("from_date") and not filters.get("to_date"):
		query += " and b.boq_date >= \'" + str(filters.from_date) + "\'"
	elif not filters.get("from_date") and filters.get("to_date"):
		query += " and b.boq_date <= \'" + str(filters.to_date) + "\'"

	query += " order by b.boq_date desc"
	return frappe.db.sql(query)
