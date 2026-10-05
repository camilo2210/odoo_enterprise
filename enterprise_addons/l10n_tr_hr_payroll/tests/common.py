# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests.common import TransactionCase


class TestL10nTrHrPayrollCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        today = date(2025, 1, 1)
        cls.turkey_company = cls.env['res.company'].create({
            'name': 'company TR',
            'street': 'Atatürk Caddesi',
            'street2': 'Seyhan Mahallesi',
            'city': 'Adana',
            'state_id': cls.env.ref('base.state_tr_01').id,
            'zip': '321123',
            'country_id': cls.env.ref('base.tr').id,
            'currency_id': cls.env.ref('base.TRY').id,
        })

        cls.env.user.company_ids |= cls.turkey_company
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.turkey_company.ids))

        cls.employee_fatma = cls.env['hr.employee'].create({
            'name': 'Fatma Arslan',
            'company_id': cls.turkey_company.id,
            'date_version': date(today.year - 2, 1, 1),
            'contract_date_start': date(today.year - 2, 1, 1),
            'contract_date_end': date(today.year - 2, 12, 31),
            'certificate': 'l10n_tr_1_illiterate',
            'identification_id': '10000000146',
            'study_field': 'Medicine',
            'l10n_tr_insurance_type': '37',
            'l10n_tr_labour_sector': '17',
            'l10n_tr_occupational_code': '2320.95',
            'l10n_tr_job_code': '1',
            'l10n_tr_graduation_year': '2020',
        })

        cls.employee_ahmed = cls.env['hr.employee'].create({
            'name': 'Ahmed Khan',
            'company_id': cls.turkey_company.id,
            'date_version': date(today.year - 1, 1, 1),
            'contract_date_start': date(today.year - 1, 1, 1),
            'contract_date_end': date(today.year - 1, 12, 31),
        })
