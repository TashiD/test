# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class DocumentApprover(Document):
	def validate(self):
		pass


	#Populate branches with active branches 
        def get_all_branches(self):
                query = """ select b.name as branch from tabBranch b, `tabCost Center` c where b.name = c.branch and b.is_disabled != 1"""
                if self.parent_cc:
                        query += " and c.parent = '{0}'".format(self.parent_cc)

                entries = frappe.db.sql(query, as_dict=True)
                self.set('items', [])

                for d in entries:
                        row = self.append('items', {})
                        row.update(d)
