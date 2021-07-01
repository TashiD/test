# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

from frappe.utils import now, now_datetime
class IssueList(Document):
	def validate(self):
		if self.status == 'Closed':
			self.resolved_by = frappe.session.user
			frappe.db.sql(""" update `tabIssue List` set docstatus = 1 where name ='{0}'""".format(self.name))
			frappe.msgprint("This issue is closed")
			self.db_set("docstatus", 1)
		if not self.requested_by:
			self.requested_by = frappe.session.user
		self.last_update = now_datetime()
		self.notify_ctm()

	def notify_ctm(self):
		subject = "ERP Issue Management"
		message = "Issue Related to '{0}' is raised in the System,  Check the system for more details".format(self.module)
		user = ['tashidorji@gyalsunginfra.bt']
		if self.module == 'Human Resources':
			user.append('thinleydema@gyalsunginfra.bt')
		if self.module in('Accounts', 'Budget Management'):
			user.append('karmatshering@gyalsunginfra.bt')
		if self.module in ('Assets Management', 'Fleet Management'):
			user.append('dorjitshering@gyalsunginfra.bt')
		if self.module == 'Material Management':
			user.append('jigmechoejur@gyalsunginfra.bt')
		if self.module == 'Projects':
			user.append('yeshinedup@gyalsunginfra.bt')

		if user:
			for a in user:
				try:
					frappe.sendmail(recipients=a, sender=None, subject=subject, message=message)
                		except:
                        		pass
