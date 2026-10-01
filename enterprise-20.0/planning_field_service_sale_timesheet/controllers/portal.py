# Part of Odoo. See LICENSE file for full copyright and licensing details.

from werkzeug.exceptions import NotFound

from odoo.http import request, route
from odoo.exceptions import AccessError, MissingError

from odoo.addons.sale.controllers.portal import CustomerPortal as SaleCustomerPortal
from odoo.addons.account.controllers.portal import CustomerPortal as AccountCustomerPortal
from odoo.addons.planning_field_service.controllers.portal import PlanningFieldServiceCustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager


class CustomerPortal(PlanningFieldServiceCustomerPortal, SaleCustomerPortal, AccountCustomerPortal):

    def _get_additional_intervention_data(self, intervention_sudo):
        intervention_data = super()._get_additional_intervention_data(intervention_sudo)
        intervention_data['show_portal_timesheets'] = request.env['account.analytic.line']._show_portal_timesheets()
        intervention_data['show_portal_materials'] = (
            intervention_sudo.sale_order_id
            and not intervention_sudo.under_warranty
            and not intervention_sudo._has_no_billable_products()
        )
        if not request.env['sale.order'].has_access('read'):
            return intervention_data
        try:
            if intervention_sudo.sale_order_id and self._document_check_access('sale.order', intervention_sudo.sale_order_id.id):
                intervention_data['intervention_link_section'].append({
                    'access_url': intervention_sudo.sale_order_id.get_portal_url(),
                    'title': request.env._('Sales Order - %(name)s', name=intervention_sudo.sale_order_id.name),
                })
        except (AccessError, MissingError):
            pass
        quotations = request.env['sale.order'].search([('planning_slot_id', '=', intervention_sudo.id), ('id', '!=', intervention_sudo.sale_order_id.id)])
        if quotations:
            if len(quotations) == 1:
                intervention_data['intervention_link_section'].append({
                    'access_url': quotations.get_portal_url(),
                    'title': request.env._('Quotation'),
                })
            else:
                intervention_data['intervention_link_section'].append({
                    'access_url': f'/my/field-service/{intervention_sudo.id}/quotes',
                    'title': request.env._('Quotations'),
                })
        return intervention_data

    @route([
        '/my/field-service/<int:intervention_id>/quotes',
    ], type='http', auth='user', website=True)
    def portal_my_field_service_interventions_quotes(self, intervention_id=None, access_token=None, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        if not self._document_check_access('planning.slot', intervention_id, access_token):
            return NotFound()
        values = self._prepare_portal_layout_values()
        SaleOrder = request.env['sale.order']
        searchbar_sortings = self._get_sale_searchbar_sortings()
        # default sortby order
        if not sortby:
            sortby = 'date'
        sort_order = searchbar_sortings[sortby]['order']
        domain = [('planning_slot_id', '=', intervention_id)]
        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]
        quotation_count = SaleOrder.search_count(domain)
        # pager
        pager = portal_pager(
            url="/my/quotes",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
            total=quotation_count,
            page=page,
            step=self._items_per_page
        )
        # content according to pager
        quotations = SaleOrder.search(domain, order=sort_order, limit=self._items_per_page, offset=pager['offset'])

        values.update({
            'date': date_begin,
            'quotations': quotations.sudo(),
            'page_name': 'quote',
            'pager': pager,
            'default_url': '/my/quotes',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        })
        return request.render('sale.portal_my_quotations', values)

    @route([
        '/my/field-service/<int:intervention_id>/invoices',
    ], type='http', auth='user', website=True)
    def portal_my_field_service_intervention_invoices(self, intervention_id=None, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):
        intervention = request.env['planning.slot'].search([('id', '=', intervention_id)])
        if not intervention.exists() or not intervention._get_timesheetable_project()._check_project_sharing_access():
            return NotFound()
        url = f'/my/field-service/{intervention_id}/invoices'
        values = self._prepare_my_invoices_values(page, date_begin, date_end, sortby, filterby, [('id', 'in', intervention.sale_order_id.sudo().invoice_ids.ids)], url)
        pager = portal_pager(**values['pager'])
        invoices = values['invoices'](pager['offset'])
        values.update(
            pager=pager,
            invoices=invoices.sudo(),
            page_name='intervention_invoices',
        )
        return request.render('account.portal_my_invoices', values)
