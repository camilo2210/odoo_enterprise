# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.http import request, route

from odoo.addons.website_sale.controllers.main import WebsiteSale


class WebsiteSaleL10nMX(WebsiteSale):

    def _l10n_mx_edi_is_mx_website(self):
        return self.env.website.company_id.account_fiscal_country_id.code == 'MX'

    @route('/shop/l10n_mx_invoicing_info', type='http', auth='public', website=True, sitemap=False)
    def l10n_mx_invoicing_info(self, **kw):
        order_sudo = request.cart
        if not self.env.website._require_mx_invoicing_details(order_sudo):
            return request.redirect(
                self.env.website._get_next_breadcrumb_step_href(
                    '/shop/l10n_mx_invoicing_info', order_sudo
                )
            )

        if redirect := self.env['website.checkout.step'].validate_checkout_progress(
            '/shop/l10n_mx_invoicing_info', order_sudo
        ):
            return request.redirect(redirect)

        partner = order_sudo.partner_invoice_id
        # '_add_customer_cfdi_values' builds the CFDI receptor from this contact.
        invoice_partner = partner if partner.type == 'invoice' else partner.commercial_partner_id

        l10n_mx_edi_fields = [
            request.env['ir.model.fields']._get('res.partner', 'l10n_mx_edi_fiscal_regime'),
            request.env['ir.model.fields']._get('account.move', 'l10n_mx_edi_usage'),
            request.env['ir.model.fields']._get('account.move', 'l10n_mx_edi_payment_method_id'),
            request.env['ir.model.fields']._get('res.partner', 'l10n_mx_edi_ieps_breakdown'),
        ]

        # === GET ===
        default_vals = {}
        if request.httprequest.method == 'GET':
            default_vals['vat'] = invoice_partner.vat
            default_vals['parent_name'] = invoice_partner.name
            default_vals['need_invoice'] = not order_sudo.l10n_mx_edi_cfdi_to_public
            default_vals['l10n_mx_edi_fiscal_regime'] = invoice_partner.l10n_mx_edi_fiscal_regime
            default_vals['l10n_mx_edi_usage'] = invoice_partner.l10n_mx_edi_usage
            default_vals['l10n_mx_edi_ieps_breakdown'] = invoice_partner.l10n_mx_edi_ieps_breakdown
            default_vals['l10n_mx_edi_payment_method_id'] = invoice_partner.l10n_mx_edi_payment_method_id

        # === POST & possibly redirect ===
        # The commercial fields belong to the whole commercial entity, so the permission is evaluated
        # on the customer of the order: an invoicing address is never a main contact.
        can_edit_commercial_fields = (
            order_sudo.partner_id._is_main_contact()
            and not (partner.vat and partner._has_confirmed_documents())
        )
        errors = {}
        if request.httprequest.method == 'POST':
            order_sudo.l10n_mx_edi_cfdi_to_public = kw.get('need_invoice') != '1'
            if kw.get('need_invoice') == '1':
                default_vals = {
                    'vat': kw.get('vat'),
                    'parent_name': kw.get('parent_name'),
                    'need_invoice': True,
                    'l10n_mx_edi_fiscal_regime': kw.get('l10n_mx_edi_fiscal_regime'),
                    'l10n_mx_edi_usage': kw.get('l10n_mx_edi_usage'),
                    'l10n_mx_edi_ieps_breakdown': kw.get('l10n_mx_edi_ieps_breakdown') == 'on',
                    'l10n_mx_edi_payment_method_id': int(kw.get('l10n_mx_edi_payment_method_id', False)) or False,
                }
                # Required fields
                if not default_vals['parent_name']:
                    errors['parent_name'] = self.env._("The company name is required")
                if not default_vals['l10n_mx_edi_fiscal_regime']:
                    errors['l10n_mx_edi_fiscal_regime'] = self.env._("The fiscal regime is required")
                if not default_vals['l10n_mx_edi_usage']:
                    errors['l10n_mx_edi_usage'] = self.env._("The usage is required")
                if not default_vals['l10n_mx_edi_payment_method_id']:
                    errors['l10n_mx_edi_payment_method_id'] = self.env._("The payment method is required")
                partner_vals = {}
                if not default_vals['vat']:
                    errors['vat'] = self.env._("The VAT number is required")
                elif can_edit_commercial_fields:
                    vat, _country_code = request.env['res.partner']._run_vat_checks(partner.country_id, default_vals['vat'], validation='setnull')
                    if not vat:
                        errors['vat'] = partner._build_vat_error_message(partner.country_id.code.lower(), default_vals['vat'], partner.name)
                    else:
                        vat, _country_code = request.env['res.partner']._run_vat_checks(partner.country_id, default_vals['vat'],
                                                                         validation=False)
                        partner_vals['vat'] = vat
                # Other fields
                partner_vals.update({
                    'l10n_mx_edi_fiscal_regime': default_vals['l10n_mx_edi_fiscal_regime'],
                    'l10n_mx_edi_ieps_breakdown': default_vals['l10n_mx_edi_ieps_breakdown'],
                    'l10n_mx_edi_usage': default_vals['l10n_mx_edi_usage'],
                    'l10n_mx_edi_payment_method_id': default_vals['l10n_mx_edi_payment_method_id'],
                })
                invoice_partner.write(partner_vals)
                if not errors:
                    order_sudo.l10n_mx_edi_usage = default_vals['l10n_mx_edi_usage']
                    order_sudo.l10n_mx_edi_payment_method_id = default_vals['l10n_mx_edi_payment_method_id']
                    parent_name_value = default_vals['parent_name']
                    if can_edit_commercial_fields and invoice_partner.name != parent_name_value:
                        invoice_partner.name = parent_name_value
                    return request.redirect(
                        self.env.website._get_next_breadcrumb_step_href(
                            '/shop/l10n_mx_invoicing_info', order_sudo
                        )
                    )
            else:
                return request.redirect(
                    self.env.website._get_next_breadcrumb_step_href(
                        '/shop/l10n_mx_invoicing_info', order_sudo
                    )
                )

        # === Render extra_info tab ===
        values = {
            'request': request,
            'website_sale_order': order_sudo,
            'post': kw,
            'partner': partner.id,
            'order': order_sudo,
            'l10n_mx_edi_fields': l10n_mx_edi_fields,
            'l10n_mx_edi_payment_methods': request.env['l10n_mx_edi.payment.method'].sudo().search([]),
            'company_country_code': order_sudo.company_id.country_id.code,
            'default_vals': default_vals,
            'errors': errors,
            # flag for rendering the 'Extra Info' dot in the wizard_checkout
            'l10n_mx_show_extra_info': True,
            'can_edit_commercial_fields': can_edit_commercial_fields,
            **self.env.website._get_checkout_step_values('/shop/l10n_mx_invoicing_info', order_sudo),
        }

        return request.render("l10n_mx_edi_website_sale.l10n_mx_edi_invoicing_info", values)
