from erpnext.tests.utils import ERPNextTestSuite
from erpnext.utilities.activation import get_level


class TestActivation(ERPNextTestSuite):
	def test_activation(self):
		levels = get_level()
		self.assertTrue(levels)
