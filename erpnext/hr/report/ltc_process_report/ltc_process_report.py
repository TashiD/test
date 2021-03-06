# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
        columns = get_columns()
        data = get_data(filters)
        return columns, data

def get_data(filters):
	if filters.uinput == "LTC":
		query =  """select t2.employee, t2.employee_name, (select tpn_number from tabEmployee e where e.name = t2.employee) as tpn, 
                t2.branch, t2.bank_name, t2.bank_ac_no, t2.amount, 0, t2.amount
                from `tabLeave Travel Concession` t1, `tabLTC Details` t2
                where t2.parent = t1.name and t1.docstatus = 1"""

	if filters.uinput == "PBVA":

		 query = """
                select t2.employee, t2.employee_name, (select tpn_number from tabEmployee e where e.name = t2.employee) as tpn,
                t2.branch, t2.bank_name, t2.bank_ac_no, t2.amount, t2.tax_amount, t2.balance_amount
                from `tabPBVA` t1, `tabPBVA Details` t2
                where t2.parent = t1.name and t1.docstatus = 1"""
	if filters.uinput == "Bonus":

		  query = """
                select t2.employee, t2.employee_name, (select tpn_number from tabEmployee e where e.name = t2.employee) as tpn,
                t2.branch, t2.bank_name, t2.bank_ac_no,  t2.amount, t2.tax_amount, t2.balance_amount 
                from `tabBonus` t1, `tabBonus Details` t2 
                where t2.parent = t1.name and t1.docstatus = 1"""
										
        if filters.get("fy"):
                query += " and t1.fiscal_year = \'"+ str(filters.fy) + "\'"
        return frappe.db.sql(query)

def get_columns():
        return [
                ("Employee ID ") + ":Link/Employee:150",
                ("Name") + ":Data:110",
                ("TPN No") + ":Data:110",
                ("Branch") + ":Data:280",
                ("Bank Name") + ":Data:100",
                ("A/C No")+ ":Data:110",
                ("Actual Amount") + ":Currency:130",
                ("TDS Amount") + ":Currency:130",
                ("Balance Amount") + ":Currency:130"
        ]

