# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
'''
--------------------------------------------------------------------------------------------------------------------------
Version          Author          CreatedOn          ModifiedOn          Remarks
------------ --------------- ------------------ -------------------  -----------------------------------------------------
1.0		  SSK		                   22/08/2016         Introducing Earned Leave Balance Lapse check.
3.0.190212       SHIV                              12/02/2019         on_cancel() method added
--------------------------------------------------------------------------------------------------------------------------                                                                          
'''

from __future__ import unicode_literals
import frappe
from frappe.utils import flt, date_diff, formatdate
from frappe import _
from frappe.model.document import Document
from erpnext.hr.utils import set_employee_name
from erpnext.hr.doctype.leave_application.leave_application import get_approved_leaves_for_period
# Ver 1.0 Begins added by SSK on 22/08/2016, Following line is added
#from erpnext.hr.doctype.leave_encashment.leave_encashment import get_le_settings
# Ver 1.0 Ends
from erpnext.custom_utils import round5

class OverlapError(frappe.ValidationError): pass
class BackDatedAllocationError(frappe.ValidationError): pass
class OverAllocationError(frappe.ValidationError): pass
class LessAllocationError(frappe.ValidationError): pass
class ValueMultiplierError(frappe.ValidationError): pass

class LeaveAllocation(Document):
	def validate(self):
		self.validate_period()
		self.validate_new_leaves_allocated_value()
		self.validate_allocation_overlap()
		self.validate_back_dated_allocation()
		self.set_total_leaves_allocated()
		self.validate_total_leaves_allocated()		
		set_employee_name(self)

	def on_update_after_submit(self):
		self.validate_new_leaves_allocated_value()
		self.set_total_leaves_allocated()
		
		frappe.db.set(self,'carry_forwarded_leaves', flt(self.carry_forwarded_leaves))
		frappe.db.set(self,'total_leaves_allocated',flt(self.total_leaves_allocated))
		
		self.validate_against_leave_applications()

        ##### Ver 3.0.190212 Begins, following method added by SHIV on 12/02/2019
        def on_cancel(self):
                self.validate_back_dated_allocation(1)
        ##### Ver 3.0.190212 Ends
        
	def validate_period(self):
		if date_diff(self.to_date, self.from_date) <= 0:
			frappe.throw(_("To date cannot be before from date"))

	def validate_new_leaves_allocated_value(self):
		"""validate that leave allocation is in multiples of 0.5"""
		round_of_leave = frappe.db.get_single_value("HR Settings", "round_of_leave")
		if round_of_leave:
			self.new_leaves_allocated = round5(self.new_leaves_allocated)
		
		balance = flt(self.new_leaves_allocated)
		if self.carry_forward and round_of_leave:
			balance = round5(self.new_leaves_allocated) + round5(self.carry_forwarded_leaves)
		else:
			balance = flt(self.new_leaves_allocated) + flt(self.carry_forwarded_leaves)

		self.total_leaves_allocated = flt(balance)

		#if flt(self.new_leaves_allocated) % 0.5:
		#	frappe.throw(_("Leaves must be allocated in multiples of 0.5"), ValueMultiplierError)

	def validate_allocation_overlap(self):
		leave_allocation = frappe.db.sql("""
			select name, from_date, to_date
			from `tabLeave Allocation`
			where employee=%s and leave_type=%s and docstatus=1
			and to_date >= %s and from_date <= %s""", 
			(self.employee, self.leave_type, self.from_date, self.to_date))

		if leave_allocation:
			frappe.msgprint(_("{0} already allocated for Employee {1} for period {2} to {3}")
				.format(self.leave_type, self.employee, formatdate(self.from_date), formatdate(self.to_date)))
			
			frappe.throw(_('Reference') + ': <a href="#Form/Leave Allocation/{0}">{0}</a>'
				.format(leave_allocation[0][0]), OverlapError)
				
	def validate_back_dated_allocation(self, cancel=0):
		future_allocation = frappe.db.sql("""select name, from_date from `tabLeave Allocation`
			where employee=%s and leave_type=%s and docstatus=1 and from_date > %s 
			and carry_forward=1""", (self.employee, self.leave_type, self.to_date), as_dict=1)
		
		if future_allocation:
                        ##### Ver 3.0.190212 Begins, by SHIV on 12/02/2019
                        # Ver 3.0.190212 Following line added
                        msg = "Leave allocation cannot be cancelled" if cancel else "Leave allocation cannot be allocated before {0}".format(formatdate(future_allocation[0].from_date))

                        # Ver 3.0.190212 Following code replaced by subsequent
                        '''
			frappe.throw(_("Leave cannot be allocated before {0}, as leave balance has already been carry-forwarded in the future leave allocation record {1}")
				.format(formatdate(future_allocation[0].from_date), future_allocation[0].name), 
					BackDatedAllocationError)
                        '''
                        frappe.throw(_("{0}, as leave balance has already been carry-forwarded in the future leave allocation record {1}")
				.format(msg, future_allocation[0].name), 
					BackDatedAllocationError)
                        ##### Ver 3.0.190212 Ends
                        
	def set_total_leaves_allocated(self):
		self.carry_forwarded_leaves = get_carry_forwarded_leaves(self.employee, 
			self.leave_type, self.from_date, self.carry_forward)

		self.total_leaves_allocated = flt(self.carry_forwarded_leaves) + flt(self.new_leaves_allocated)

		# Ver 1.0 Begins added by SSK on 22/08/2016, following block is added
		if self.leave_type == 'Earned Leave' :
                        #le = get_le_settings()                                                                                 # Line commented by SHIV on 2018/10/12
                        le = frappe.get_doc("Employee Group",frappe.db.get_value("Employee",self.employee,"employee_group"))    # Line added by SHIV on 2018/10/12
                        if flt(self.total_leaves_allocated) > flt(le.encashment_lapse):
                                frappe.msgprint(_("Earned Leave Balance {0}/{1} for Employee: {2} is lapsed.")\
                                        .format((flt(self.total_leaves_allocated)-flt(le.encashment_lapse)),flt(self.total_leaves_allocated),self.employee))
                                self.total_leaves_allocated = le.encashment_lapse
		# Ver 1.0 Ends

                # Following code commented by SHIV on 2018/10/15
                """
		if not flt(self.total_leaves_allocated):
			frappe.throw(_("Total leaves allocated is mandatory"))
		"""

	def validate_total_leaves_allocated(self):
		# Adding a day to include To Date in the difference
		date_difference = date_diff(self.to_date, self.from_date) + 1
		if flt(date_difference) < flt(self.new_leaves_allocated):
			frappe.throw(_("Total allocated leaves are more than days in the period"), OverAllocationError)

                # Following code added by SHIV on 2018/10/15
		if not flt(self.total_leaves_allocated):
			frappe.throw(_("Total leaves allocated is mandatory"))
			
	def validate_against_leave_applications(self):
		leaves_taken = get_approved_leaves_for_period(self.employee, self.leave_type, 
			self.from_date, self.to_date)
		
		if flt(leaves_taken) > flt(self.total_leaves_allocated):
			frappe.throw(_("Total allocated leaves {0} cannot be less than already approved leaves {1} for the period").format(self.total_leaves_allocated, leaves_taken), LessAllocationError)

@frappe.whitelist()
def get_carry_forwarded_leaves(employee, leave_type, date, carry_forward=None):
	carry_forwarded_leaves = 0
	
	if carry_forward:
		validate_carry_forward(leave_type)
		
		previous_allocation = frappe.db.sql("""
			select name, from_date, to_date, total_leaves_allocated
			from `tabLeave Allocation`
			where employee=%s and leave_type=%s and docstatus=1 and to_date < %s
			order by to_date desc limit 1
		""", (employee, leave_type, date), as_dict=1)
		if previous_allocation:
			leaves_taken = get_approved_leaves_for_period(employee, leave_type, 
				previous_allocation[0].from_date, previous_allocation[0].to_date)
		
			carry_forwarded_leaves = flt(previous_allocation[0].total_leaves_allocated) - flt(leaves_taken)
			
	return carry_forwarded_leaves
		
def validate_carry_forward(leave_type):
	if not frappe.db.get_value("Leave Type", leave_type, "is_carry_forward"):
		frappe.throw(_("Leave Type {0} cannot be carry-forwarded").format(leave_type))

