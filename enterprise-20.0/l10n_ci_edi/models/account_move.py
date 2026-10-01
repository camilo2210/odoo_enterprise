from datetime import datetime

from markupsafe import Markup

from odoo import api, fields, models
from odoo.tools.float_utils import json_float_round
from werkzeug.urls import url_quote


class AccountMove(models.Model):
    _inherit = 'account.move'

    # === FNE Technical Fields === #
    l10n_ci_edi_fne_invoice_id = fields.Char(
        string="FNE Invoice Id",
        copy=False,
        readonly=True,
        help="FNE invoice id.",
    )
    l10n_ci_edi_fne_qrcode = fields.Char(
        string="FNE QR Code URL",
        copy=False,
        readonly=True,
    )
    l10n_ci_edi_fne_qrcode_img = fields.Html(
        string="FNE QR Code",
        compute='_compute_l10n_ci_edi_fne_qrcode_img',
    )
    l10n_ci_edi_fne_datetime = fields.Datetime(
        string="FNE Validation Time",
        copy=False,
        readonly=True,
        help="Date and time of FNE validation.",
    )
    l10n_ci_edi_fne_status = fields.Selection(
        selection=[
            ('sent', 'Sent'),
            ('error', 'Error'),
        ],
        string="FNE Status",
        copy=False,
        readonly=True,
        tracking=True,
    )
    l10n_ci_edi_validation_messages = fields.Json(
        compute='_compute_l10n_ci_edi_validation_messages',
        compute_sudo=True,
    )
    l10n_ci_edi_fne_payment_method = fields.Selection(
        selection=[
            ("cash", "Cash"),
            ("card", "Bank Card"),
            ("check", "Check"),
            ("mobile-money", "Mobile Money"),
            ("transfer", "Bank Transfer"),
            ("deferred", "Deferred Payment"),
        ],
        string="FNE Payment Method",
    )
    l10n_ci_edi_fne_reference = fields.Char(string="FNE Reference", copy=False, readonly=True)
    l10n_ci_edi_fne_rne = fields.Char(string="RNE", copy=False, help="Receipt number issued through TERNE(Electronic Standardized Receipt Issuing Terminal)")
    l10n_ci_edi_is_needed = fields.Boolean(
        string="FNE Is Needed",
        compute='_compute_l10n_ci_edi_is_needed',
    )

    # === Computes === #

    @api.depends('l10n_ci_edi_fne_qrcode')
    def _compute_l10n_ci_edi_fne_qrcode_img(self):
        for move in self:
            if move.l10n_ci_edi_fne_qrcode:
                move.l10n_ci_edi_fne_qrcode_img = Markup(
                    '<img src="/report/barcode/?barcode_type=QR&amp;value={qr_url}&amp;width=200&amp;height=200" alt="FNE QR Code"/>'
                ).format(qr_url=url_quote(move.l10n_ci_edi_fne_qrcode, safe=''))
            else:
                move.l10n_ci_edi_fne_qrcode_img = False

    @api.depends('company_id', 'country_code', 'move_type', 'l10n_ci_edi_fne_invoice_id')
    def _compute_l10n_ci_edi_is_needed(self):
        for move in self:
            move.l10n_ci_edi_is_needed = (
                move.company_id.root_id.l10n_ci_edi_is_active
                and move.country_code == 'CI'
                and move.move_type in ('out_invoice', 'out_refund')
                and not move.l10n_ci_edi_fne_invoice_id
            )

    @api.depends('l10n_ci_edi_fne_invoice_id')
    def _compute_show_reset_to_draft_button(self):
        super()._compute_show_reset_to_draft_button()
        self.filtered(lambda m: m.l10n_ci_edi_fne_invoice_id).show_reset_to_draft_button = False

    def button_draft(self):
        self.l10n_ci_edi_fne_status = False
        return super().button_draft()

    @api.depends(
        'country_code',
        'move_type',
        'reversed_entry_id',
        'l10n_ci_edi_fne_payment_method',
        'commercial_partner_id',
        'company_id',
        'invoice_line_ids',
    )
    def _compute_l10n_ci_edi_validation_messages(self):
        for move in self:
            if not move.move_type in ('out_invoice', 'out_refund') or move.country_code != 'CI':
                move.l10n_ci_edi_validation_messages = False
                continue

            messages = {}

            if not move.company_id.root_id.l10n_ci_edi_is_active:
                messages['fne_configuration_warning'] = {
                    'message': move.env._(
                        "FNE configuration is incomplete for company '%(company)s'. "
                        "Please configure the FNE Server Mode and API Token in Settings.",
                        company=move.company_id.name,
                    ),
                    'blocking': True,
                }
                move.l10n_ci_edi_validation_messages = messages
                continue

            if move.move_type == 'out_invoice':
                if move.commercial_partner_id and move.commercial_partner_id.is_company and not move.commercial_partner_id.vat:
                    messages['missing_vat'] = {
                        'message': move.env._("The customer NCC (Tax ID) is required for FNE e-invoicing."),
                        'blocking': True,
                    }
                if move.commercial_partner_id and not move.commercial_partner_id.phone:
                    messages['missing_phone'] = {
                        'message': move.env._("The customer phone is required for FNE e-invoicing."),
                        'blocking': True,
                    }
                if move.commercial_partner_id and not move.commercial_partner_id.email:
                    messages['missing_email'] = {
                        'message': move.env._("The customer email is required for FNE e-invoicing."),
                        'blocking': True,
                    }
                if not move.l10n_ci_edi_fne_payment_method:
                    messages['missing_payment_method'] = {
                        'message': move.env._("The FNE payment method is required for FNE e-invoicing."),
                        'blocking': True,
                    }

            if move.move_type == 'out_refund' and not move.reversed_entry_id:
                messages['missing_origin_invoice'] = {
                    'message': move.env._("Credit notes must reference the original invoice for FNE compliance."),
                    'blocking': True,
                }

            if move.move_type == 'out_refund' and move.reversed_entry_id:
                if not move.reversed_entry_id.l10n_ci_edi_fne_invoice_id:
                    messages['origin_not_sent'] = {
                        'message': move.env._("The original invoice must be sent to FNE before its credit note can be sent."),
                        'blocking': True,
                    }
                elif any(not line.l10n_ci_edi_fne_item_id for line in move._l10n_ci_edi_get_product_lines()):
                    messages['missing_item_id'] = {
                        'message': move.env._("One or more lines do not have an item ID, you should reverse the original invoice after being sent to FNE."),
                        'blocking': True,
                    }

            move.l10n_ci_edi_validation_messages = messages

    def _l10n_ci_edi_get_product_lines(self):
        """Return product lines sorted by id for deterministic ordering."""
        return self.invoice_line_ids.filtered(lambda l: l.display_type == 'product').sorted('id') - self.invoice_line_ids._get_discount_lines()

    # === Business Methods === #

    def _l10n_ci_edi_prepare_invoice_payload(self):
        self.ensure_one()
        company = self.company_id

        # Prepare line items
        items = []
        product_lines = self._l10n_ci_edi_get_product_lines()
        for index, line in enumerate(product_lines, start=1):
            tax_codes = []
            custom_taxes = []
            for tax in line.tax_ids:
                if code := tax.l10n_ci_edi_tax_code:
                    tax_codes.append(code)
                else:
                    # Custom / unrecognized tax: send name and amount
                    custom_taxes.append({'name': tax.name, 'amount': tax.amount})
            items.append({
                'reference': str(index),
                'description': line.label,
                'quantity': line.quantity,
                'amount': json_float_round(line.price_unit, self.currency_id.decimal_places),
                'taxes': tax_codes,
                'customTaxes': custom_taxes,
                'discount': json_float_round(line.discount, 2),
                'measurementUnit': line.product_uom_id.name,
            })

        # Compute invoice-level discount as a percentage of the untaxed total
        discount_lines = self.invoice_line_ids._get_discount_lines()
        discount_amount = abs(sum(discount_lines.mapped('amount_currency')))
        subtotal_before_discount = sum(product_lines.mapped('price_subtotal'))
        global_discount = json_float_round(discount_amount / subtotal_before_discount * 100, 2) if subtotal_before_discount else 0

        # Prepare the main payload
        template = self._l10n_ci_edi_get_template()
        payload = {
            'invoiceType': 'sale',
            'paymentMethod': self.l10n_ci_edi_fne_payment_method,
            'template': template,
            'isRne': bool(self.l10n_ci_edi_fne_rne),
            'rne': self.l10n_ci_edi_fne_rne or '',
            'clientNcc': self.commercial_partner_id.vat or '',
            'clientCompanyName': self.commercial_partner_id.name,
            'clientPhone': self.commercial_partner_id.phone,
            'clientEmail': self.commercial_partner_id.email,
            'clientSellerName': company.name,
            'pointOfSale': company.name,
            'establishment': company.name,
            'foreignCurrency': self.currency_id.name if template == 'B2F' else '',
            'foreignCurrencyRate': self.invoice_currency_rate if template == 'B2F' else 0.0,
            'discount': global_discount,
            'items': items,
        }

        return payload

    def _l10n_ci_edi_prepare_credit_note_payload(self):
        self.ensure_one()
        return {
            'items': [
                {
                    'id': line.l10n_ci_edi_fne_item_id,
                    'quantity': line.quantity,
                }
                for line in self._l10n_ci_edi_get_product_lines()
                if line.l10n_ci_edi_fne_item_id
            ],
        }

    def _l10n_ci_edi_get_template(self):
        if self.env.ref('l10n_ci_edi.res_partner_category_government') in self.commercial_partner_id.category_id:
            return "B2G"
        elif self.commercial_partner_id.country_code != "CI":
            return "B2F"
        elif self.commercial_partner_id.is_company:
            return "B2B"
        else:
            return "B2C"

    def _l10n_ci_edi_send(self):
        """Send the move to the FNE system.

        Returns a tuple (data, error).
        """
        self.ensure_one()
        locked_move = self.try_lock_for_update()
        if not locked_move:
            return None, {
                'code': 'LOCKED',
                'message': self.env._("Invoice is already being processed by another user."),
            }

        if locked_move.move_type == 'out_refund':
            return locked_move._l10n_ci_edi_send_credit_note()
        return locked_move._l10n_ci_edi_send_invoice()

    def _l10n_ci_edi_send_invoice(self):
        """Send an invoice or bill to the FNE system."""
        self.ensure_one()
        company = self.company_id

        payload = self._l10n_ci_edi_prepare_invoice_payload()
        # FNE credentials are configured on the root company; branches authenticate through it.
        data, error = company.root_id._l10n_ci_edi_api_call('/external/invoices/sign', payload)

        if error:
            self.l10n_ci_edi_fne_status = 'error'
            self.message_post(body=self.env._("FNE submission returned the following error:\n %(error)s", error=error['message']))
            return None, error

        self.write({
            'l10n_ci_edi_fne_invoice_id': data.get('invoice', {}).get('id'),
            'l10n_ci_edi_fne_reference': data.get('reference'),
            'l10n_ci_edi_fne_qrcode': data.get('token'),
            'l10n_ci_edi_fne_datetime': datetime.fromisoformat(data['invoice']['date']).replace(tzinfo=None) if data.get('invoice', {}).get('date') else False,
            'l10n_ci_edi_fne_status': 'sent',
        })
        if data.get('warning'):
            self.message_post(body=self.env._("FNE sticker balance is low: %(warning)s", warning=data['warning']))
        # Map returned FNE item IDs back to move lines using the reference
        product_lines = self._l10n_ci_edi_get_product_lines()
        ref_to_line = {str(index): line for index, line in enumerate(product_lines, start=1)}
        for item_data in data.get('invoice', {}).get('items', []):
            if line := ref_to_line.get(item_data.get('reference')):
                line.l10n_ci_edi_fne_item_id = item_data.get('id')
        return data, None

    def _l10n_ci_edi_send_credit_note(self):
        """Send a credit note to the FNE system.

        Returns a tuple (data, error).
        """
        self.ensure_one()
        company = self.company_id

        payload = self._l10n_ci_edi_prepare_credit_note_payload()
        original_fne_id = self.reversed_entry_id.l10n_ci_edi_fne_invoice_id
        endpoint = f'/external/invoices/{url_quote(original_fne_id, safe="")}/refund'
        # FNE credentials are configured on the root company; branches authenticate through it.
        data, error = company.root_id._l10n_ci_edi_api_call(endpoint, payload)

        if error:
            self.l10n_ci_edi_fne_status = 'error'
            self.message_post(body=self.env._("FNE submission returned the following error:\n %(error)s", error=error['message']))
            return None, error

        self.write({
            'l10n_ci_edi_fne_reference': data.get('reference'),
            'l10n_ci_edi_fne_qrcode': data.get('token'),
            'l10n_ci_edi_fne_status': 'sent',
        })
        if data.get('warning'):
            self.message_post(body=self.env._("FNE sticker balance is low: %(warning)s", warning=data['warning']))
        return data, None
