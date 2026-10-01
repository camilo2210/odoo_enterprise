from odoo.fields import Date
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


class TestEsAccountReportsCommon(TestAccountReportsCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestAccountReportsCommon.setup_country('es')
    def setUpClass(cls):
        super().setUpClass()

        cls.spanish_partner = cls.env['res.partner'].create({
            'name': "Bernardo Ganador",
            'street': "Avenida de los Informes Financieros, 42",
            'zip': 4242,
            'city': "Madrid",
            'country_id': cls.env.ref('base.es').id,
            'state_id': cls.env.ref('base.state_es_m').id,
            'vat': "ESA12345674",
        })

        base_tags = (
            cls.env.ref('l10n_es.mod_111_casilla_02_balance')
            + cls.env.ref('l10n_es.mod_115_casilla_02_balance')
            + cls.env.ref('l10n_es.mod_303_casilla_01_balance')
        )._get_matching_tags()
        base_refund_tags = (
            cls.env.ref('l10n_es.mod_111_casilla_02_balance')
            + cls.env.ref('l10n_es.mod_115_casilla_02_balance')
            + cls.env.ref('l10n_es.mod_303_casilla_14_aeat_mod_303_14_sale_balance')
        )._get_matching_tags()
        tax_tags = (
            cls.env.ref('l10n_es.mod_111_casilla_03_balance')
            + cls.env.ref('l10n_es.mod_115_casilla_03_balance')
            + cls.env.ref('l10n_es.mod_303_casilla_03_balance')
        )._get_matching_tags()
        tax_refund_tags = (
            cls.env.ref('l10n_es.mod_111_casilla_03_balance')
            + cls.env.ref('l10n_es.mod_115_casilla_03_balance')
            + cls.env.ref('l10n_es.mod_303_casilla_15_balance')
        )._get_matching_tags()

        cls.spanish_test_tax = cls.env['account.tax'].create({
            'name': "Test ES BOE tax",
            'amount_type': 'percent',
            'amount': 42,
            'invoice_repartition_line_ids': [
                (0, 0, {
                    'repartition_type': 'base',
                    'tag_ids': base_tags.ids,
                }),

                (0, 0, {
                    'repartition_type': 'tax',
                    'tag_ids': tax_tags.ids,
                })
            ],
            'refund_repartition_line_ids': [
                (0, 0, {
                    'repartition_type': 'base',
                    'tag_ids': base_refund_tags.ids,
                }),

                (0, 0, {
                    'repartition_type': 'tax',
                    'tag_ids': tax_refund_tags.ids,
                })
            ],
        })

        cls.env.company.vat = "ESA12345674"

    def _check_boe_export(self, modelo_number, additional_context=None, wizard_values=None):
        account_return = self.env['account.return'].create({
            'name': 'Tax Return',
            'type_id': self.env.ref(f'l10n_es_reports.es_mod{modelo_number}_tax_return_type').id,
            'company_id': self.company.id,
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        })
        context = additional_context or {}
        wizard = self.env[f'l10n_es_reports.mod{modelo_number}.submission.wizard'].with_context(**context).create({
            'return_id': account_return.id
        })

        if wizard_values:
            wizard.write(wizard_values)
        with self.allow_pdf_render():
            account_return.action_submit()
            wizard.action_proceed_with_submission()

        boe_file = account_return.attachment_ids.filtered(lambda a: a.name.endswith(".txt"))

        self.assertTrue(boe_file.raw.size, f"BOE generation returned empty for modelo {modelo_number}")

        return boe_file  # For additional checks

    def _get_report_boe(self, report, modelo_number, options):
        account_return = self.env['account.return'].create({
            'name': 'Tax Return',
            'type_id': self.env.ref(f'l10n_es_reports.es_mod{modelo_number}_tax_return_type').id,
            'company_id': self.env.company.id,
            'date_from': options['date']['date_from'],
            'date_to': options['date']['date_to'],
        })
        date_from = Date.from_string(options['date']['date_from'])
        date_to = Date.from_string(options['date']['date_to'])
        options = self._generate_options(report, date_from, date_to)
        wizard = self.env[f'l10n_es_reports.mod{modelo_number}.submission.wizard'] \
            .with_context(default_date_from=date_from, default_date_to=date_to, options=options) \
            .create({'return_id': account_return.id})
        options['l10n_es_reports_boe_wizard_id'] = wizard.id
        tax_report_handler = self.env[f'l10n_es.mod{modelo_number}.tax.report.handler']
        boe_file = tax_report_handler.export_boe(options)
        boe_file['file_content'] = boe_file['file_content'].decode()
        return boe_file
