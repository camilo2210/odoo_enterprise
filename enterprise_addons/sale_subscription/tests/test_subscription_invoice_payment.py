# Part of Odoo. See LICENSE file for full copyright and licensing details.

from werkzeug import urls

from odoo.tests import tagged, HttpCase

from odoo.addons.payment.tests.common import PaymentCommon
from odoo.addons.sale_subscription.tests.common_sale_subscription import TestSubscriptionCommon


@tagged('post_install', '-at_install')
class TestSubscriptionInvoicePayment(TestSubscriptionCommon, PaymentCommon, HttpCase):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.enable_post_process_patcher = False

    def test_link_payment_to_invoice_when_portal_payment(self):
        subscription = self.subscription.create({
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'payment_token_id': self.payment_token.id,
            'sale_order_template_id': self.subscription_tmpl.id,
        })

        subscription._onchange_sale_order_template_id()
        subscription.action_confirm()

        bank_journal = self.company_data['default_journal_bank']

        dummy_provider = self.env['payment.provider'].create({
            'name': "Dummy Provider",
            'code': 'none',
            'journal_id': bank_journal.id,
            'is_published': True,
            'payment_method_ids': [self.payment_method_id],
            'allow_tokenization': True,
            'redirect_form_view_id': self.env['ir.ui.view'].search([('type', '=', 'qweb')], limit=1).id,
        })

        data = {
            'provider_id': dummy_provider.id,
            'payment_method_id': self.payment_method_id,
            'token_id': None,
            'amount': subscription.amount_total,
            'flow': 'direct',
            'tokenization_requested': False,
            'landing_route': subscription.get_portal_url(),
            'access_token': subscription.access_token,
        }
        url = self._build_url("/my/orders/%s/transaction" % subscription.id)
        self.make_jsonrpc_request(url, data)

        self._update_transaction(subscription.transaction_ids, state="done")
        subscription.transaction_ids.provider_id.journal_id.inbound_payment_method_line_ids[0].write({
            'payment_provider_id': dummy_provider.id,
        })
        self._run_post_processing()

        self.assertEqual(subscription.invoice_ids.matched_payment_ids, subscription.transaction_ids.payment_id)
        expected_payment_state = self.env['account.move']._get_invoice_in_payment_state()
        self.assertEqual(subscription.invoice_ids.payment_state, expected_payment_state)

    def test_link_payment_to_invoice_when_payment_to_default_account(self):
        subscription = self.subscription.create({
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'payment_token_id': self.payment_token.id,
            'sale_order_template_id': self.subscription_tmpl.id,
        })

        subscription._onchange_sale_order_template_id()
        subscription.action_confirm()

        bank_journal = self.company_data['default_journal_bank']

        dummy_provider = self.env['payment.provider'].create({
            'name': "Dummy Provider",
            'code': 'none',
            'journal_id': bank_journal.id,
            'is_published': True,
            'payment_method_ids': [self.payment_method_id],
            'allow_tokenization': True,
            'redirect_form_view_id': self.env['ir.ui.view'].search([('type', '=', 'qweb')], limit=1).id,
        })

        data = {
            'provider_id': dummy_provider.id,
            'payment_method_id': self.payment_method_id,
            'token_id': None,
            'amount': subscription.amount_total,
            'flow': 'direct',
            'tokenization_requested': False,
            'landing_route': subscription.get_portal_url(),
            'access_token': subscription.access_token,
        }
        url = self._build_url("/my/orders/%s/transaction" % subscription.id)
        self.make_jsonrpc_request(url, data)

        self._update_transaction(subscription.transaction_ids, state="done")
        subscription.transaction_ids.provider_id.journal_id.inbound_payment_method_line_ids[0].write({
            'payment_provider_id': dummy_provider.id,
            'payment_account_id': bank_journal.default_account_id.id,
        })
        self._run_post_processing()

        self.assertEqual(subscription.invoice_ids.matched_payment_ids, subscription.transaction_ids.payment_id)
        self.assertEqual(subscription.invoice_ids.payment_state, "paid")

    # Helper
    def _build_url(self, route):
        return urls.url_join(self.base_url(), route)
