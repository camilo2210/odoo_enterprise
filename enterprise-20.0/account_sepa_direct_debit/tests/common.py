from odoo import fields
from odoo.addons.account_direct_debit.tests.common import AccountDirectDebitCommon


class SDDTestCommon(AccountDirectDebitCommon):
    _test_user_groups = (
        *AccountDirectDebitCommon._test_user_groups,
        'account.group_account_manager',  # configuring the bank journal
    )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref('base.EUR').active = True

        cls.env.user.email = "ruben.rybnik@sorcerersfortress.com"

        cls.country_belgium, cls.country_china, cls.country_germany = cls.env['res.country'].search([('code', 'in', ['BE', 'CN', 'DE'])], limit=3, order='name ASC')

        # We setup our test company
        cls.sdd_company = cls.company
        cls.sdd_company.country_id = cls.country_belgium
        cls.sdd_company.city = 'Company 1 City'
        cls.sdd_company.sdd_creditor_identifier = 'BE30ZZZ300D000000042'
        cls.sdd_company_bank_journal = cls.journal
        # comp_bank_account1 is already trusted, sudo to bypass the lock
        cls.sdd_company_bank_journal.sudo().bank_account_number = 'CH9300762011623852957'
        sdd_method_line = cls.sdd_company_bank_journal.inbound_payment_method_line_ids.filtered(lambda l: l.code == 'sdd')
        sdd_method_line.payment_account_id = cls.inbound_payment_method_line.payment_account_id

        # Then we setup the banking data and mandates of two customers (one with a one-off mandate, the other with a recurrent one)
        cls.partner_agrolait = cls.env['res.partner'].create({'name': 'Agrolait', 'city': 'Agrolait Town', 'country_id': cls.country_germany.id})
        cls.partner_bank_agrolait = cls.create_account('DE44500105175407324931', cls.partner_agrolait, 'ING', 'BBRUBEBB')
        cls.mandate_agrolait = cls.create_mandate(cls.partner_agrolait, cls.partner_bank_agrolait, False, cls.sdd_company)
        cls.mandate_agrolait.action_validate_mandate()

        cls.partner_china_export = cls.env['res.partner'].create({'name': 'China Export', 'city': 'China Town', 'country_id': cls.country_china.id})
        cls.partner_bank_china_export = cls.create_account('SA0380000000608010167519', cls.partner_china_export, 'BNP Paribas', 'GEBABEBB')
        cls.mandate_china_export = cls.create_mandate(cls.partner_china_export, cls.partner_bank_china_export, True, cls.sdd_company)
        cls.mandate_china_export.action_validate_mandate()

        cls.partner_no_bic = cls.env['res.partner'].create({'name': 'NO BIC Co', 'city': 'NO BIC City', 'country_id': cls.country_belgium.id})
        cls.partner_bank_no_bic = cls.create_account('BE68844010370034', cls.partner_no_bic, 'NO BIC BANK', None)
        cls.mandate_no_bic = cls.create_mandate(cls.partner_no_bic, cls.partner_bank_no_bic, True, cls.sdd_company)
        cls.mandate_no_bic.action_validate_mandate()

        # Finally, we create one invoice for each of our test customers ...
        cls.basic_product = cls.env['product.product'].create({'name': 'A Test Product'})
        cls.invoice_agrolait = cls._create_invoice_sepa(cls.partner_agrolait)
        cls.invoice_china_export = cls._create_invoice_sepa(cls.partner_china_export)
        cls.invoice_no_bic = cls._create_invoice_sepa(cls.partner_no_bic)

        # Pay the invoices with mandates
        cls.pay_with_mandate(cls.invoice_agrolait)
        cls.pay_with_mandate(cls.invoice_china_export)
        cls.pay_with_mandate(cls.invoice_no_bic)

    @classmethod
    def create_account(cls, number, partner, bank_name, bank_bic):
        return cls.env['res.partner.bank'].create({
            'account_number': number,
            'partner_id': partner.id,
            'bank_name': bank_name,
            'bank_bic': bank_bic,
            'allow_out_payment': True,
        })

    @classmethod
    def create_mandate(cls, partner, partner_bank, one_off=False, company=None, scheme='CORE'):
        return cls._create_mandate(
            validate=False,
            mandate_type='sepa',
            partner_bank_id=partner_bank.id,
            one_off=one_off,
            start_date=fields.Date.today(),
            partner_id=partner.id,
            company_id=(company or cls.env.company).id,
            sdd_scheme=scheme,
        )

    @classmethod
    def _create_invoice_sepa(cls, partner):
        return cls._create_invoice_one_line(
            partner_id=partner,
            currency_id=cls.env.ref('base.EUR').id,
            payment_reference='invoice to client',
            product_id=cls.basic_product,
            price_unit=42,
            name='something',
            post=True,
        )

    @classmethod
    def pay_with_mandate(cls, invoice):
        sdd_method_line = cls.journal.inbound_payment_method_line_ids.filtered(lambda l: l.code == 'sdd')
        return cls._register_payment(
            invoice,
            payment_date=invoice.invoice_date_due or invoice.invoice_date,
            journal_id=cls.journal.id,
            payment_method_line_id=sdd_method_line.id,
        )

    @classmethod
    def reconcile_payments(cls, payments):
        for payment in payments:
            st_line = cls.env['account.bank.statement.line'].create({
                'amount': payment.amount,
                'date': fields.Date.context_today(payment.mandate_id),
                'payment_ref': 'test',
                'journal_id': cls.journal.id,
            })
            st_suspense_lines = st_line._seek_for_lines()[1]
            liquidity_line = payment._seek_for_lines()[0]
            st_suspense_lines.account_id = liquidity_line.account_id
            (st_suspense_lines + liquidity_line).reconcile()
