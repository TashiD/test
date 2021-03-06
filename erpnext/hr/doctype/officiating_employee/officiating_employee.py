# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import getdate, nowdate
from frappe.utils.data import add_days

class OfficiatingEmployee(Document):
	def validate(self):
		if self.employee == self.officiate:
			frappe.throw("Both Employee and Officiating Employee can not be same person")

		#em_list = frappe.db.sql("select employee, employee_name from tabEmployee where status = 'Active' and reports_to = \'" + str(self.employee) + "\'", as_dict=True)
		#self.set('items', [])

		#for d in em_list:
		#	row = self.append('items', {})
		#	row.update(d)

	def on_submit(self):
		#if self.items:
		#	for a in self.items:	
		#		emp = frappe.get_doc("Employee", a.employee)
		#		emp.db_set("reports_to", self.officiate)

		user = frappe.get_doc("User", frappe.db.get_value("Employee", self.officiate, "user_id"))
		user.flags.ignore_permissions = True

		if "Approver" not in user.get("user_roles"):
			user.add_roles("Approver")
			self.db_set("already", 0)
		else:
			self.db_set("already", 1)

		emp = frappe.get_doc("Employee", self.officiate)
		emp.db_set("reports_to", frappe.db.get_value("Employee", self.employee, "reports_to"))
		emp.db_set("approver_name", frappe.db.get_value("Employee", self.employee, "approver_name"))
		#self.sendmail()

	def revoke_perm(self):
		#for a in self.items:	
		#	emp = frappe.get_doc("Employee", a.employee)
		#	emp.db_set("reports_to", self.employee)
		#frappe.throw(str(getdate(nowdate())))
		if self.revoked:
			frappe.throw("Already Revoked")
		if getdate(self.to_date) > getdate(nowdate()):
			self.db_set("to_date", nowdate())

		self.db_set("revoked", 1)
		if not self.already:
			user = frappe.get_doc("User", frappe.db.get_value("Employee", self.officiate, "user_id"))
			user.flags.ignore_permissions = True
			user.remove_roles("Approver")

		emp = frappe.get_doc("Employee", self.officiate)
		emp.db_set("reports_to", self.employee)			
		emp.db_set("approver_name", self.employee_name)			

		frappe.msgprint("Permissions Revoked")


	def sendmail(self):
		designation = frappe.get_doc("Employee", self.employee).designation
		message = " Mr/Ms <b> {0} </b> will officiate <b> {1} </b> from {2} to {3} as {4}""".format(self.officiate_name, self.employee_name, self.from_date, self.to_date, designation) 
                for email in frappe.db.sql(""" select user_id from `tabEmployee` 
			where reports_to = '{0}'""".format(self.employee), as_dict = 1):
                	if email.user_id:
                        	try:
                                	frappe.sendmail(recipients=email.user_id, sender=None, subject=Officiating, message=message)
                        	except:
                                	pass

def check_off_exp():
	off = frappe.db.sql("""select name from `tabOfficiating Employee` 
		where docstatus = 1 and to_date = %(today)s""", {"today": add_days(nowdate(), -1)}, as_dict=True)
	for a in off:
		print(str(a))
		doc = frappe.get_doc("Officiating Employee", a)
		doc.revoke_perm()	
	
