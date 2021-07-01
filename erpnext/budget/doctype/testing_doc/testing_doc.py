# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class TestingDoc(Document):
	def validate(self):
		frappe.msgprint("Validate")
		url = self.get_url()
		frappe.msgprint("{0}".format(url))
	def submit(self):
		frappe.msgprint("Submit")

