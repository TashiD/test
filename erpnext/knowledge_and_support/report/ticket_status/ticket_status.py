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
                ("Name") + ":Link/Issue List:200",
                ("Issue Name") + ":Data:270",
                ("Posting Date")+ ":Date:140",
                ("Module") + ":Data:120",
		("Priority") + ":Data:120",
                ("Requested By") + ":Data:120",
		("Status") + ":Data:120",
		("Resolved By") + ":Data:120"
        ]

def get_data(filters):
	cond = " 1 = 1"
	if filters.branch:
		cond += " and il.branch = '{}'".format(filters.get("branch"))
	
	if filters.from_date and filters.to_date:
		cond += " and il.posting_date between '{0}' and '{1}'".format(filters.get("from_date"), filters.get("to_date"))
	
	if filters.module_name:
		cond += " and module = '{0}'".format(filters.get("module_name"))

	if filters.status:
		cond += " and status = '{0}'".format(filters.get("status")) 	
		
        data =  frappe.db.sql("""select il.name, il.issue_name, il.posting_date, il.module, il.priority, il.requested_by_name, 
			il.status, il.resolved_by_name from `tabIssue List` as il  where {0}""".format(cond))
        return data

