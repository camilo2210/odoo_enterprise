from odoo import Command
from odoo.addons.account_iso20022.tests.test_iso20022_common import TestISO20022CommonCreditTransfer
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestISO20022ForceSepaForEur(TestISO20022CommonCreditTransfer):
    """ A journal whose own currency isn't EUR never gets the SEPA Credit Transfer payment method offered
    (it's restricted to EUR journals), so a EUR payment made from it falls back to the generic ISO20022
    payment method. By default that method always reports SvcLvl=NURG/ChrgBr=SHAR. The
    'account_iso20022.force_sepa_for_eur' system parameter lets such EUR batches be treated as genuine
    SEPA Credit Transfers instead, similar to the existing 'iso20022_ch_force_sepa' mechanism.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref('base.EUR').active = True
        cls.env.user.group_ids |= cls.env.ref('account.group_validate_bank_account')
        cls.payment_method = cls.env.ref('account_iso20022.account_payment_method_iso20022')
        cls.bank_journal = cls.company_data['default_journal_bank']
        cls.bank_journal.write({
            'bank_account_number': 'BE48363523682327',
            'bank_name': 'ING',
            'bank_bic': 'BBRUBEBB',
            'available_payment_method_ids': [Command.link(cls.payment_method.id)],
        })
        cls.payment_method_line = cls.env['account.payment.method.line'].sudo().create([{
            'name': cls.payment_method.name,
            'payment_method_id': cls.payment_method.id,
            'journal_id': cls.bank_journal.id,
        }])
        cls.env['res.partner.bank'].create({
            'partner_id': cls.partner_a.id,
            'account_number': 'BE08429863697813',
            'allow_out_payment': True,
            'bank_name': 'ING',
            'bank_bic': 'BBRUBEBB',
        })
        # A country is required for sepa transfer
        cls.partner_a.country_id = cls.env.ref('base.us')

        # The journal keeps its default (non-EUR) currency, so SEPA Credit Transfer is never offered on it;
        # only the individual payment is made in EUR.
        assert cls.bank_journal.currency_id.name != 'EUR'

    def _create_eur_payment_batch(self):
        payment = self.create_payment(
            self.bank_journal,
            self.partner_a,
            None,
            500,
        )
        payment.currency_id = self.env.ref('base.EUR')
        payment.action_post()

        batch = self.env['account.batch.payment'].create({
            'journal_id': self.bank_journal.id,
            'payment_ids': [Command.link(payment.id)],
            'payment_method_id': self.payment_method.id,
            'batch_type': 'outbound',
        })
        batch.validate_batch()
        return self.get_sct_doc_from_batch(batch)

    def test_eur_payment_uses_nurg_by_default(self):
        """ Without the parameter, a EUR payment through the generic ISO20022 method keeps reporting
        SvcLvl=NURG/ChrgBr=SHAR."""
        sct_doc = self._create_eur_payment_batch()
        svc_lvl = sct_doc.find('.//{*}PmtInf/{*}PmtTpInf/{*}SvcLvl/{*}Cd').text
        charge_bearer = sct_doc.find('.//{*}PmtInf/{*}ChrgBr').text

        self.assertEqual(svc_lvl, 'NURG')
        self.assertEqual(charge_bearer, 'SHAR')

    def test_eur_payment_uses_sepa_when_forced(self):
        """ With the parameter enabled, a EUR payment through the generic ISO20022 method is reported
        as a genuine SEPA Credit Transfer. """
        self.env['ir.config_parameter'].sudo().set_bool('account_iso20022.force_sepa_for_eur', True)

        sct_doc = self._create_eur_payment_batch()
        svc_lvl = sct_doc.find('.//{*}PmtInf/{*}PmtTpInf/{*}SvcLvl/{*}Cd').text
        charge_bearer = sct_doc.find('.//{*}PmtInf/{*}ChrgBr').text

        self.assertEqual(svc_lvl, 'SEPA')
        self.assertEqual(charge_bearer, 'SLEV')

    def test_non_eur_payment_unaffected_when_forced(self):
        """ The parameter only affects EUR batches; a payment in the journal's own currency keeps
        reporting SvcLvl=NURG/ChrgBr=SHAR even when the parameter is enabled. """
        self.env['ir.config_parameter'].sudo().set_bool('account_iso20022.force_sepa_for_eur', True)

        payment = self.create_payment(
            self.bank_journal,
            self.partner_a,
            None,
            500,
        )
        payment.action_post()

        batch = self.env['account.batch.payment'].create({
            'journal_id': self.bank_journal.id,
            'payment_ids': [Command.link(payment.id)],
            'payment_method_id': self.payment_method.id,
            'batch_type': 'outbound',
        })
        batch.validate_batch()
        sct_doc = self.get_sct_doc_from_batch(batch)
        svc_lvl = sct_doc.find('.//{*}PmtInf/{*}PmtTpInf/{*}SvcLvl/{*}Cd').text
        charge_bearer = sct_doc.find('.//{*}PmtInf/{*}ChrgBr').text

        self.assertEqual(svc_lvl, 'NURG')
        self.assertEqual(charge_bearer, 'SHAR')
