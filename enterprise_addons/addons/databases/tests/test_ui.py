from odoo.tests import new_test_user, patch, tagged
from odoo.addons.base.tests.common import HttpCase


@tagged('-at_install', 'post_install')
class TestDatabasesUi(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.startClassPatcher(patch('odoo.addons.databases.api.OdooDatabaseApi.invite_users'))

    def test_ui(self):
        new_test_user(self.env, 'joel@barish.tld', name='Joel Barish')
        self.start_tour('/odoo', 'databases_tour', login='admin')
