from odoo import api, models
from odoo.fields import Domain
from odoo.tools import email_normalize


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    def _inverse_partner_phone(self):
        # Don't overwrite the partner's phone when set from the website form.
        if not self.env.context.get('from_website_form'):
            return super()._inverse_partner_phone()

    def website_form_input_filter(self, request, values):
        params = request.params
        partner = self._website_form_find_or_create_partner(params)
        values.update(
            partner_id=partner.id,
            start_datetime=False,
            end_datetime=False,
        )
        if (form_phone := params.get('partner_phone')) != partner.phone:
            values['partner_phone'] = form_phone
            request.update_context(from_website_form=True)
        return values

    def _website_form_find_or_create_partner(self, params):
        identity_domains = []
        if normalized := email_normalize(params.get('partner_email')):
            identity_domains.append([('email_normalized', '=', normalized)])
        if phone := params.get('partner_phone'):
            identity_domains.append([('phone_mobile_search', '=', phone)])
        candidates = self.env['res.partner'].sudo().search(
            Domain.AND([*identity_domains, [('company_id', 'in', [False, self.env.company.id])]])
        ) if identity_domains else False
        if not candidates:
            if not (params.get('partner_name') or params.get('partner_email')):
                return self.env['res.partner']
            return self._website_form_create_partner(params, parent=False)

        address_domain = [
            ('street', '=ilike', params.get('street')),
            ('street2', '=ilike', params.get('street2')),
            ('city', '=ilike', params.get('city')),
            ('zip', '=ilike', params.get('zip')),
            ('country_id', '=', int(params.get('country_id') or 0) or False),
            ('state_id', '=', int(params.get('state_id') or 0) or False),
        ]
        if match := candidates.filtered_domain(address_domain):
            return match[0]
        child = self.env['res.partner'].sudo().search(
            [('parent_id', 'in', candidates.ids), ('type', '=', 'delivery'), *address_domain],
            limit=1,
        )
        return child or self._website_form_create_partner(params, parent=candidates[0])

    def _website_form_create_partner(self, params, parent):
        vals = {
            'name': params.get('partner_name') or params.get('partner_email'),
            'street': params.get('street'),
            'street2': params.get('street2'),
            'city': params.get('city'),
            'zip': params.get('zip'),
            'country_id': int(params.get('country_id') or 0) or False,
            'state_id': int(params.get('state_id') or 0) or False,
        }
        if parent:
            vals.update(parent_id=parent.id, type='delivery')
        else:
            vals.update(
                phone=params.get('partner_phone'),
                email=params.get('partner_email'),
            )
        partner = self.env['res.partner'].sudo().create(vals)
        partner._ensure_geolocalized()
        return partner

    @api.model
    def _show_portal_field_service(self):
        """
        Determine if we show field service information in the portal.
        """
        entry = self.env.ref("planning_field_service.portal_field_service", raise_if_not_found=False)
        return bool(entry and entry.show_in_portal)
