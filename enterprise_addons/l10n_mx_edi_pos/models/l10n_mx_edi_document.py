from odoo import api, Command, fields, models


class L10n_Mx_EdiDocument(models.Model):
    _inherit = 'l10n_mx_edi.document'

    pos_order_ids = fields.Many2many(
        comodel_name='pos.order',
        relation='l10n_mx_edi_pos_order_document_ids_rel',
        column1='document_id',
        column2='pos_order_id',
        copy=False,
        readonly=True,
        check_company=True,
    )

    def _get_source_records(self):
        # EXTENDS 'l10n_mx_edi'
        self.ensure_one()
        return super()._get_source_records() or self.pos_order_ids

    @api.model
    def _update_document_sat_state(self, sat_state, error=None):
        # EXTENDS 'l10n_mx_edi'
        if super()._update_document_sat_state(sat_state, error=error):
            return True

        if self.pos_order_ids and self.state in ('invoice_sent', 'invoice_cancel'):
            self.pos_order_ids._l10n_mx_edi_cfdi_refund_update_sat_state(self, sat_state, error=error)
            return True

    @api.model
    def _get_update_sat_status_domains(self, from_cron=True):
        # EXTENDS 'l10n_mx_edi'
        results = super()._get_update_sat_status_domains(from_cron=from_cron)

        if not from_cron:
            # POS documents that may need SAT status update
            results.append([
                ('state', 'in', ('ginvoice_sent', 'invoice_sent')),
                ('pos_order_ids', 'any', [
                    ('l10n_mx_edi_cfdi_state', 'in', ('global_sent', 'sent')),
                    ('l10n_mx_edi_cfdi_sat_state', '!=', 'cancelled'),
                ]),
                ('sat_state', '=', 'valid'),
            ])

        return results

    def _create_update_document(self, records, document_values, accept_method):
        # EXTENDS 'l10n_mx_edi'
        # sudo because accounting users don't have access to pos.order
        pos_order_ids_cmd = document_values.pop('pos_order_ids', None)
        result = super()._create_update_document(records, document_values, accept_method)
        if pos_order_ids_cmd:
            result.sudo().write({'pos_order_ids': pos_order_ids_cmd})
        return result

    @api.model
    def _create_update_invoice_document_from_invoice(self, invoice, document_values):
        # EXTENDS 'l10n_mx_edi'
        # Link POS orders to the document when creating/updating from an invoice.
        invoice_sudo = invoice.sudo()
        if invoice_sudo.pos_order_ids:
            document_values['pos_order_ids'] = [Command.set(invoice_sudo.pos_order_ids.ids)]
        return super()._create_update_invoice_document_from_invoice(invoice, document_values)

    @api.model
    def _create_update_invoice_document_from_pos_order(self, order, document_values):
        """ Create/update a new document for pos order.

        :param order:           A pos order.
        :param document_values: The values to create the document.
        """
        if document_values['state'] in ('invoice_sent', 'invoice_cancel'):
            accept_method_state = f"{document_values['state']}_failed"
        else:
            accept_method_state = document_values['state']

        document = order.l10n_mx_edi_document_ids._create_update_document(
            order,
            document_values,
            lambda x: x.state == accept_method_state,
        )

        order.l10n_mx_edi_document_ids \
            .filtered(lambda x: x != document and x.state in {
                'invoice_sent_failed',
                'invoice_cancel_failed',
                'ginvoice_sent_failed',
                'ginvoice_cancel_failed',
            }) \
            .unlink()

        if document.state in ('invoice_sent', 'invoice_cancel'):
            order.l10n_mx_edi_document_ids \
                .filtered(lambda x: (
                    x != document
                    and x.sat_state not in ('valid', 'cancelled', 'skip')
                    and x.attachment_uuid == document.attachment_uuid
                )) \
                .write({'sat_state': 'skip'})

        return document

    @api.model
    def _create_update_global_invoice_document_from_pos_orders(self, orders, document_values):
        """ Create/update a new document for global invoice.

        :param orders:          The related pos orders.
        :param document_values: The values to create the document.
        """
        if document_values['state'] in ('ginvoice_sent', 'ginvoice_cancel'):
            accept_method_state = f"{document_values['state']}_failed"
        else:
            accept_method_state = document_values['state']

        document = orders[0].l10n_mx_edi_document_ids._create_update_document(
            self,
            document_values,
            lambda x: x.state == accept_method_state,
        )

        orders[0].l10n_mx_edi_document_ids \
            .filtered(lambda x: x != document and x.state in {'ginvoice_sent_failed', 'ginvoice_cancel_failed'}) \
            .unlink()

        if document.state in ('ginvoice_sent', 'ginvoice_cancel'):
            orders.l10n_mx_edi_document_ids \
                .filtered(lambda x: (
                    x != document
                    and x.sat_state not in ('valid', 'cancelled', 'skip')
                    and x.attachment_uuid == document.attachment_uuid
                )) \
                .write({'sat_state': 'skip'})

        return document
