from odoo import Command

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon

REPORT_PERIOD_START_DATE = '2025-01-01'
REPORT_PERIOD_END_DATE = '2025-12-31'


class TestL10nFrReportsCommon(TestAccountReportsCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        base_fr = cls.env.ref('base.fr')

        cls.env.user.phone = '0033123456789'

        cls.firm = cls.env['res.partner'].create({
            'country_id': base_fr.id,
            'name': 'Test Firm',
            'vat': 'FR23334175221',
            'l10n_fr_siret': '78467169500087',
            'street': '10 Business Ave',
            'zip': '75002',
            'city': 'Paris',
        })

        cls.company.partner_id.city = 'Paris'
        cls.company.write({
            'country_id': base_fr.id,
            'street': '1 Enterprise Street',
            'zip': '75002',
            'l10n_fr_siret': '71204961800739',
            'ape': '6201Z',
            'account_representative_id': cls.firm.id,
            'l10n_fr_das2_activity': 'Testing DAS2 Flows',
            'totals_below_sections': False,
            'account_fiscal_country_id': base_fr.id,
        })

        cls.partner_a.write({
            'vat': 'FR23334175221',
            'l10n_fr_siret': '50056940503239',
            'country_id': base_fr.id,
            'street': '123 Main Street',
            'zip': '75001',
            'city': 'Paris',
            'l10n_fr_profession_id': cls.env.ref('l10n_fr_reports.l10n_fr_res_partner_profession_web_developer').id,
            'birth_date': '1999-07-24',
        })

        cls.partner_b.write({
            'country_id': cls.env.ref('base.de').id,
            'street': '456 Side Street',
            'zip': '69001',
            'city': 'Berlin',
            'l10n_fr_profession_id': cls.env.ref('l10n_fr_reports.l10n_fr_res_partner_profession_marketing_consultant').id,
            'birth_date': '1999-07-31',
        })

        cls.fees_account = cls.env['account.account'].create({
            'name': 'Fees Account',
            'code': '424242',
            'tag_ids': [
                Command.link(cls.env.ref('l10n_fr_reports.account_tag_das2_fees').id),
            ],
            'account_type': 'expense_other',
        })

        cls.copyright_account = cls.env['account.account'].create({
            'name': 'Copyright Account',
            'code': '434343',
            'tag_ids': [
                Command.link(cls.env.ref('l10n_fr_reports.account_tag_das2_copyright').id),
            ],
            'account_type': 'expense_other',
        })

    def _generate_move(self, move_type='in_invoice', partner=None, amount=None, account=None):
        return self.env['account.move'].create({
            'move_type': move_type,
            'partner_id': partner.id if partner else self.partner_a.id,
            'invoice_date': '2025-06-15',
            'line_ids': [
                Command.create({
                    'account_id': account.id if account else self.fees_account.id,
                    'quantity': 1,
                    'price_unit': amount or 2401,
                }),
            ],
        })

    def _generate_options(self, report=False, date_from=REPORT_PERIOD_START_DATE, date_to=REPORT_PERIOD_END_DATE):
        if not report:
            report = self.report
        return super()._generate_options(report, date_from, date_to)
