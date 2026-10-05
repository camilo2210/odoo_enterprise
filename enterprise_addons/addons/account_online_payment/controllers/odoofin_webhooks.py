from odoo.http import Controller, request, route


class OdooFinWebhooksController(Controller):

    @route('/webhook/odoofin/payment_activated', type='jsonrpc', auth='public', methods=['POST'])
    def payments_activated(self):
        data = request.get_json_data()
        if link := request.env['account.online.link'].sudo().search([('client_id', '=', data.get('client_id'))], limit=1):
            if template := request.env(su=True).ref('account_online_payment.mail_template_account_payment_activation_success', raise_if_not_found=False):
                template.send_mail(link.id, force_send=True, email_values={'email_to': link.renewal_contact_email, 'email_from': link.renewal_contact_email})
            link.is_payment_activated = True
        return True

    @route('/webhook/odoofin/payment_status_updated', type='jsonrpc', auth='public', methods=['POST'])
    def payment_status_updated(self):
        """ This webhook route will be called by Odoo Fin proxy to update payment status.
            The payment status is never passed via the webhook, the webhook is used to warn
            the odoo database that we have a pending data to be fetched.
            The route will first make sure that we at least have a link with the passed
            client_id and that we have either an open payment, either an open batch payment
            with the passed payment_identifier.
            To trigger the cron, we also make sure that we don't have an existing one awaiting
            to be triggered as the cron will fetch the status for all payments and we don't want
            to make duplicate calls.
        """
        data = request.get_json_data()
        # First make sure we have at least a link and an open payment/batch, then trigger the cron.
        has_odoofin_link = data.get('client_id') and request.env['account.online.link'].sudo().search_count([('client_id', '=', data['client_id'])], limit=1)
        has_payments = has_batch_payments = False
        if payment_identifier := data.get('payment_identifier'):
            domain = [
                ('state', '!=', 'reconciled'),
                ('journal_id.account_online_link_id.is_payment_activated', '=', True),
                ('payment_online_status', 'in', ('unsigned', 'pending')),
                ('payment_identifier', '=', payment_identifier),
            ]
            has_payments = request.env['account.payment'].sudo().search_count(domain, limit=1)
            has_batch_payments = request.env['account.batch.payment'].sudo().search_count(domain, limit=1)

        if has_odoofin_link and (has_payments or has_batch_payments):
            cron = request.env.ref('account_online_payment.ir_cron_bank_sync_update_payment_status').sudo()
            has_cron_trigger = request.env['ir.cron.trigger'].sudo().search([('cron_id', '=', cron.id)], limit=1)
            if not has_cron_trigger:
                cron._trigger()
        return True

    @route('/webhook/odoofin/update_audit_status', type='jsonrpc', auth='public', methods=['POST'], readonly=False)
    def update_audit_status(self):
        data = request.get_json_data()
        if link := request.env['account.online.link'].sudo().search([('client_id', '=', data.get('client_id'))], limit=1):
            link._update_connection_status()
        return True
