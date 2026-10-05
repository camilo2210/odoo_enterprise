import odoo
from odoo.addons.point_of_sale.tests.common import TestPoSCommon
from unittest.mock import patch
from odoo.addons.l10n_at_pos.models.fiskaly_client import FiskalyClient
from odoo import Command


@odoo.tests.tagged('post_install', '-at_install', 'post_install_l10n')
class TestPoSBasicConfig(TestPoSCommon):
    _test_user_groups = None  # FIXME list needed groups

    def test_fiskaly_at_auth(self):
        limited_user = self.env['res.users'].create({
            'name': 'another accountant',
            'login': 'another_accountant',
            'password': 'another_accountant',
            'group_ids': [
                Command.set(self.env.ref('account.group_account_user').ids),
            ],
        })
        with patch('requests.post') as mock_post:
            mock_response = mock_post.return_value
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {'access_token': 'mocked_token_123'}
            fiskaly_client = FiskalyClient(self.env.company.with_user(limited_user), False, False)
            self.l10n_at_fiskaly_access_token = fiskaly_client.auth()
