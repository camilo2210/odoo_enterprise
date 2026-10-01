# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _
from odoo.http import request, route
from odoo.tools import single_email_re

from odoo.addons.website_sale.controllers.main import WebsiteSale


class L10nCLWebsiteSale(WebsiteSale):

    def _checkout_invoice_info_form_empty(self, **kw):
        return [key for key, value in kw.items() if value.strip() == '']

    def _checkout_invoice_info_form_validate(self, order, **kw):
        errors = {}
        if kw.get('l10n_cl_type_document') == 'invoice' and order.partner_id.country_id.code != 'CL':
            errors['cl'] = _('You need to be a resident of Chile in order to request an invoice')
        if kw.get('l10n_cl_dte_email') and not single_email_re.match(kw.get('l10n_cl_dte_email')):
            errors['dte_email'] = _('Invalid DTE email! Please enter a valid email address.')
        return errors

    def _get_default_value_invoice_info(self, order, **kw):
        return {
            'l10n_cl_type_document': kw.get('l10n_cl_type_document', 'ticket'),
            'l10n_cl_activity_description': kw.get('l10n_cl_activity_description', order.partner_id.l10n_cl_activity_description),
            'l10n_cl_dte_email': kw.get('l10n_cl_dte_email', ''),
        }

    def _l10n_cl_update_order(self, order, **kw):
        partner = order.partner_invoice_id
        if kw.get('l10n_cl_type_document') == 'ticket':
            partner.l10n_cl_sii_taxpayer_type = '3'
        elif kw.get('l10n_cl_type_document') == 'invoice':
            partner.l10n_cl_sii_taxpayer_type = '1'
            partner.l10n_cl_activity_description = kw.get('l10n_cl_activity_description')
            partner.l10n_cl_dte_email = kw.get('l10n_cl_dte_email')

    @route('/shop/l10n_cl_invoicing_info', type='http', auth='public', methods=['GET', 'POST'], website=True, sitemap=False)
    def l10n_cl_invoicing_info(self, **kw):
        order_sudo = request.cart
        if redirect := self.env['website.checkout.step'].validate_checkout_progress(
            '/shop/l10n_cl_invoicing_info', order_sudo
        ):
            return request.redirect(redirect)

        values = {
            'website_sale_order': order_sudo,
            'l10n_cl_show_extra_info': True,
            'default_value': kw,
            'errors_fields': self._checkout_invoice_info_form_validate(order_sudo, **kw),
            'errors_empty': self._checkout_invoice_info_form_empty(**kw),
            **self.env.website._get_checkout_step_values('/shop/l10n_cl_invoicing_info', order_sudo),
        }
        next_checkout_step_href = values['next_website_checkout_step_href']

        if request.httprequest.method == 'POST':
            if (values['errors_fields'] or values['errors_empty']) and kw['l10n_cl_type_document'] != 'ticket':
                return request.render("l10n_cl_edi_website_sale.l10n_cl_edi_invoicing_info", values)
            self._l10n_cl_update_order(order_sudo, **kw)
            return request.redirect(next_checkout_step_href)
        # httprequest.method GET
        if order_sudo.partner_id.country_id.code != 'CL':
            order_sudo.partner_invoice_id = request.env.ref('l10n_cl.par_cfa')
            return request.redirect(next_checkout_step_href)
        if 'l10n_cl_type_document' not in values['default_value']:
            values['default_value'].update(l10n_cl_type_document='ticket')
        return request.render('l10n_cl_edi_website_sale.l10n_cl_edi_invoicing_info', values)
