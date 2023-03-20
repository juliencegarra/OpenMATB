from core.dialog import Dialog

class Errors:
	def __init__(self):
		self.errors_list = list()
		self.errors_str = str()
		self.some_fatals = False
		self.win = None

	def add_error(self, error_msg, fatal=False):
		if len(self.errors_list) == 0:
			self.errors_list.append(_('There were some errors:'))
		self.errors_list.append('– ' + error_msg)

		# Fatal message has not been added yet
		if self.some_fatals == False and fatal == True:
			self.errors_list[0] = self.errors_list[0] + _(' (some fatals)')
			self.some_fatals = True

	def is_empty(self):
		len(self.errors_list) == 0

	def show_errors(self):
		if self.win is not None:
			if not self.is_empty():
				buttons = [_('Continue'), _('Exit')] if not self.some_fatals else [_('Exit')]
				self.win.add_dialog("Errors", self.errors_list, buttons=buttons, exit_button=_('Exit'))

errors = Errors()