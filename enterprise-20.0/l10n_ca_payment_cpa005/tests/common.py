from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.account_direct_debit.tests.common import AccountDirectDebitCommon


class CPA005Common(AccountDirectDebitCommon):
    _test_user_groups = (
        *AccountDirectDebitCommon._test_user_groups,
        'account.group_account_manager',  # configuring the journal
    )

    @classmethod
    @AccountTestInvoicingCommon.setup_country('ca')
    def setUpClass(cls):
        super().setUpClass()
        cls.quick_ref('base.CAD').active = True
        cls.company.write({
            'l10n_ca_cpa005_short_name': 'COMP_NAME',
            'name': 'Long Company Name',
        })

        cls.journal.inbound_payment_method_line_ids |= cls.env['account.payment.method.line'].create(
            {'payment_method_id': cls.env.ref('l10n_ca_payment_cpa005.account_payment_method_cpa005_pad').id}
        )
        cls.journal.outbound_payment_method_line_ids |= cls.env['account.payment.method.line'].create(
            {'payment_method_id': cls.env.ref('l10n_ca_payment_cpa005.account_payment_method_cpa005').id}
        )
        cls.journal.write({
            'l10n_ca_cpa005_originator_id': '1234567890',
            'l10n_ca_cpa005_destination_data_center': '01600',
        })
        cls.pad_line = cls.journal.inbound_payment_method_line_ids.filtered(lambda line: line.code == 'cpa005')[:1]
        cls.eft_line = cls.journal.outbound_payment_method_line_ids.filtered(lambda line: line.code == 'cpa005')[:1]
        # comp_bank_account1 is already trusted, sudo to bypass the lock on its number
        cls.comp_bank_account1.sudo().write({
            'account_number': '9999999',
            'l10n_ca_financial_institution_number': '022233333',
        })

        # The counterparties: payors of the PADs, payees of the EFTs
        (cls.partner_a + cls.partner_b).country_id = cls.quick_ref('base.ca')
        cls.bank_partner_a = cls._create_ca_bank(
            partner_id=cls.partner_a,
            account_number='333333333',
            l10n_ca_financial_institution_number='055566666',
        )
        cls.bank_partner_b = cls._create_ca_bank(
            partner_id=cls.partner_b,
            account_number='444444444',
            l10n_ca_financial_institution_number='077788888',
        )

        cls.code_pad = cls.env['l10n_ca_cpa005.transaction.code'].search([('code', '=', '700')], limit=1)

    @classmethod
    def _create_ca_bank(cls, **create_vals):
        create_vals = {
            'allow_out_payment': True,
            **create_vals,
        }
        cls._prepare_record_kwargs('res.partner.bank', create_vals)
        return cls.env['res.partner.bank'].create(create_vals)

    @classmethod
    def _create_cpa005_mandate(cls, **create_vals):
        return cls._create_mandate(**{
            'mandate_type': 'cpa005_pad',
            'partner_id': cls.partner_a,
            'partner_bank_id': cls.bank_partner_a,
            'l10n_ca_cpa005_pad_category': 'business',
            **create_vals,
        })

    @classmethod
    def _create_cpa005_payment(cls, **create_vals):
        """ A posted CPA 005 payment: a PAD collection (inbound) or an EFT deposit (outbound). """
        payment_type = create_vals.get('payment_type', 'inbound')
        create_vals = {
            'partner_id': cls.partner_a,
            'journal_id': cls.journal,
            'payment_method_line_id': cls.pad_line if payment_type == 'inbound' else cls.eft_line,
            'currency_id': cls.quick_ref('base.CAD'),
            'l10n_ca_cpa005_transaction_code_id': cls.code_pad,
            **create_vals,
        }
        cls._prepare_record_kwargs('account.payment', create_vals)
        payment = cls.env['account.payment'].create(create_vals)
        payment.action_post()
        return payment
