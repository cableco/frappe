import frappe
from frappe.desk.form.linked_with import get_linked_doctypes
from frappe.patches.v11_0.replicate_old_user_permissions import get_doctypes_to_skip

# `skip_for_doctype` was a un-normalized way of storing for which
# doctypes the user permission was applicable.
# in this patch, we normalize this into `applicable_for` where
# a new record will be created for each doctype where the user permission
# is applicable
#
# if the user permission is applicable for all doctypes, then only
# one record is created

def execute():
	frappe.reload_doctype('User Permission')

	# to check if we need to migrate from skip_for_doctype
	has_skip_for_doctype = frappe.db.has_column("User Permission", "skip_for_doctype")
	skip_for_doctype_map = {}

	new_user_permissions_list = []

	user_permissions_to_delete = []

	for user_permission in frappe.get_all('User Permission', fields=['*']):
		if has_skip_for_doctype:
			if not user_permission.skip_for_doctype:
				frappe.db.set_value('User Permission', user_permission.name, 'apply_to_all_doctypes', 1)
				continue
			skip_for_doctype = user_permission.skip_for_doctype.split('\n')
		else:
			if skip_for_doctype_map[(user_permission.allow, user_permission.user)] == None:
				skip_for_doctype = get_doctypes_to_skip(user_permission.allow, user_permission.user)
				# cache skip for doctype for same user and doctype
				skip_for_doctype_map[(user_permission.allow, user_permission.user)] = skip_for_doctype
			else:
				skip_for_doctype = skip_for_doctype_map[(user_permission.allow, user_permission.user)]

		if skip_for_doctype:
			# only specific doctypes are selected
			# split this into multiple records and delete
			linked_doctypes = get_linked_doctypes(user_permission.allow, True).keys()
			applicable_for_doctypes = list(set(linked_doctypes) - set(skip_for_doctype))

			user_permissions_to_delete.append(user_permission.name)
			user_permission.name = None
			user_permission.skip_for_doctype = None
			for doctype in applicable_for_doctypes:
				if doctype:
					# Maintain sequence (name, user, allow, for_Value, applicable_for)
					new_user_permissions_list.append((
						frappe.generate_hash("", 10),
						user_permission.user,
						user_permission.allow,
						user_permission.for_value,
						doctype
					))


	if new_user_permissions_list:
		print(len(new_user_permissions_list))
		frappe.db.sql('INSERT INTO `tabUser Permission` (`name`, `user`, `allow`, `for_value`, `applicable_for`) VALUES {}'.format(
			','.join(['%s'] * len(new_user_permissions_list))
		), tuple(new_user_permissions_list))

	if user_permissions_to_delete:
		print(len(user_permissions_to_delete))
		frappe.db.sql('DELETE FROM `tabUser Permission` WHERE `name` in ({})'
			.format(','.join(['%s'] * len(user_permissions_to_delete))),
			tuple(user_permissions_to_delete)
		)