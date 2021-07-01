# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	data = """ select name, image from `tabItem` where name = '100167'"""
	da = []
	for a in frappe.db.sql(data, as_dict = 1):
	 	da.append(a.name)
		c = '<img src="{{ {0} }}"/>'.format(a.image)
		da.append(c)

	columns = get_columns()

	return columns, da



def get_columns():
        columns = [
                ("Item")+":Link/Item:100",
                ("Item Name")+":Image:150"
                ]

	return columns
