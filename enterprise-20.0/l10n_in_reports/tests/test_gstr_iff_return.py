from odoo.tests import tagged
from datetime import date
from odoo.addons.l10n_in_reports.tests.common import L10nInTestAccountReportsCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class L10nInTestGstrIffReturn(L10nInTestAccountReportsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_b.l10n_in_gst_treatment = 'regular'
        cls.partner_foreign.l10n_in_gst_treatment = 'overseas'
        cls.consumer_partner = cls.partner_a.copy({
            'vat': False,
            'l10n_in_gst_treatment': 'consumer',
        })
        cls.default_company.write({
            'account_return_periodicity': 'trimester',
        })
        cls.gstr_iff_return_type = 'l10n_in_reports.in_gstr_iff_return_type'
        cls.gstr1_return_type = 'l10n_in_reports.in_gstr1_return_type'

    def test_iff_json_and_quarterly_gstr1_carry_forward(self):

        def _create_return(return_type_xmlid, start_date, end_date):
            return self.env['account.return'].create({
                'name': 'IN Tax Return',
                'type_id': self.env.ref(return_type_xmlid).id,
                'company_id': self.default_company.id,
                'date_from': start_date,
                'date_to': end_date,
            })

        m1_b2b_reported = self._init_inv(partner=self.partner_b, taxes=self.comp_igst_18, line_vals={'price_unit': 500, 'quantity': 1}, invoice_date=date(2026, 1, 5))
        m1_b2b_missed = self._init_inv(partner=self.partner_b, taxes=self.comp_igst_18, line_vals={'price_unit': 100, 'quantity': 1}, invoice_date=date(2026, 1, 6))
        m1_b2b_missed.l10n_in_gstr_iff_exclude = True

        m1_credit_note_reported = self._create_credit_note(inv=m1_b2b_reported, line_vals={'price_unit': 250, 'quantity': 1}, credit_note_date=date(2026, 1, 8))
        m1_credit_note_missed = self._create_credit_note(inv=m1_b2b_missed, line_vals={'price_unit': 50, 'quantity': 1}, credit_note_date=date(2026, 1, 9))
        m1_credit_note_missed.l10n_in_gstr_iff_exclude = True

        self._init_inv(partner=self.consumer_partner, taxes=self.sgst_sale_18, invoice_date=date(2026, 1, 11))
        self._init_inv(partner=self.partner_foreign, taxes=self.igst_sale_18_exp, invoice_date=date(2026, 1, 12))

        # Generate monthly GSTR IFF JSON
        iff_m1 = _create_return(self.gstr_iff_return_type, date(2026, 1, 1), date(2026, 1, 31))
        iff_m1_json = iff_m1._get_l10n_in_gstr1_json()

        self.compare_dict_ignoring_list_order(iff_m1_json, self._read_mock_json('gstr_iff_month1_expected_json.json'))
        iff_m1.l10n_in_gstr1_status = 'sent'

        self.assertTrue(m1_b2b_reported.l10n_in_iff_reported)
        self.assertTrue(m1_credit_note_reported.l10n_in_iff_reported)

        self.assertFalse(m1_b2b_missed.l10n_in_iff_reported)
        self.assertFalse(m1_credit_note_missed.l10n_in_iff_reported)
        m3_b2b_reported = self._init_inv(partner=self.partner_b, taxes=self.comp_igst_18, line_vals={'price_unit': 500, 'quantity': 1}, invoice_date=date(2026, 3, 5))
        m3_b2b_missed = self._init_inv(partner=self.partner_b, taxes=self.comp_igst_18, line_vals={'price_unit': 100, 'quantity': 1}, invoice_date=date(2026, 3, 6))
        m3_b2b_missed.l10n_in_gstr_iff_exclude = True

        self._create_credit_note(inv=m3_b2b_reported, line_vals={'price_unit': 250, 'quantity': 1}, credit_note_date=date(2026, 3, 8))
        m3_credit_note_missed = self._create_credit_note(inv=m3_b2b_missed, line_vals={'price_unit': 50, 'quantity': 1}, credit_note_date=date(2026, 3, 9))
        m3_credit_note_missed.l10n_in_gstr_iff_exclude = True

        # Generate quarterly GSTR-1 JSON
        gstr1_quarterly = _create_return(self.gstr1_return_type, date(2026, 1, 1), date(2026, 3, 31))
        gstr1_quarterly_json = gstr1_quarterly._get_l10n_in_gstr1_json()

        self.compare_dict_ignoring_list_order(gstr1_quarterly_json, self._read_mock_json('gstr1_quarterly_expected_json.json'))
