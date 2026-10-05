# Part of Odoo. See LICENSE file for full copyright and licensing details.

from freezegun import freeze_time

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nUsW2(TransactionCase):

    @freeze_time('2026-01-01')
    def test_generate_csv_when_no_date_end_is_given(self):
        self.env.company.country_id = self.env.ref('base.us').id

        w2 = self.env['l10n.us.w2'].create({"date_end": False})
        w2.action_generate_csv()

        self.assertEqual(w2.csv_file.filename, 'form_w2_2026.csv')
        self.assertEqual(w2.payslip_ids, self.env['hr.payslip'])
