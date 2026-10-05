from odoo.addons.account.tests.common import AccountTestInvoicingWithBanksCommon


class AccountDirectDebitCommon(AccountTestInvoicingWithBanksCommon):
    _test_user_groups = (
        'base.group_partner_manager',
        'account.group_account_user',
        'account.group_validate_bank_account',
    )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.journal = cls.company_data['default_journal_bank']
        cls.journal.bank_account_id = cls.comp_bank_account1
        cls.partner_a.country_id = cls.quick_ref('base.be')  # mandate validation requires a country

    @classmethod
    def _create_mandate(cls, validate=True, **create_vals):
        create_vals = {
            'partner_id': cls.partner_a.id,
            'partner_bank_id': cls.partner_bank_account1.id,
            'company_id': cls.company.id,
            **create_vals,
        }
        cls._prepare_record_kwargs('account.direct.debit.mandate', create_vals)
        mandate = cls.env['account.direct.debit.mandate'].create(create_vals)
        if validate:
            mandate.action_validate_mandate()
        return mandate

    @classmethod
    def _create_batch_payment(cls, payments, batch_type='inbound', **create_vals):
        return cls.env['account.batch.payment'].create({
            'journal_id': cls.journal.id,
            'batch_type': batch_type,
            'payment_ids': payments,
            **create_vals,
        })
