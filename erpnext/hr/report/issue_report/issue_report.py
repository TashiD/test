# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	columns, data = [], []
	return columns, data


def get_columns(leave_types):
        columns = [
                _("Issue List") + ":Link/Issue List:120",
                _("Issue Name") + "::150",
                _("Posting Date") +"::150",
                _("Priority") +"::160",
                _("Employment Type") +"::160",

        ]

        for leave_type in leave_types:
                columns.append(_(leave_type) + " " + _("Taken") + ":Float:160")
                columns.append(_(leave_type) + " " + _("Balance") + ":Float:160")

        return columns

def get_data(filters, leave_types):

