# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from markupsafe import Markup
from urllib.parse import urlencode

from odoo import models, fields, _, api
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_repr

from .fedex_request import FedexRequest


_logger = logging.getLogger(__name__)


FEDEX_STOCK_TYPE = [
    ('PAPER_4X6', 'PAPER_4X6'),
    ('PAPER_4X675', 'PAPER_4X675'),
    ('PAPER_4X8', 'PAPER_4X8'),
    ('PAPER_4X9', 'PAPER_4X9'),
    ('PAPER_7X475', 'PAPER_7X475'),
    ('PAPER_85X11_BOTTOM_HALF_LABEL', 'PAPER_85X11_BOTTOM_HALF_LABEL'),
    ('PAPER_85X11_TOP_HALF_LABEL', 'PAPER_85X11_TOP_HALF_LABEL'),
    ('PAPER_LETTER', 'PAPER_LETTER'),
    ('STOCK_4X6', 'STOCK_4X6'),
    ('STOCK_4X675_LEADING_DOC_TAB', 'STOCK_4X675_LEADING_DOC_TAB'),
    ('STOCK_4X675_TRAILING_DOC_TAB', 'STOCK_4X675_TRAILING_DOC_TAB'),
    ('STOCK_4X8', 'STOCK_4X8'),
    ('STOCK_4X9', 'STOCK_4X9'),
    ('STOCK_4X9_LEADING_DOC_TAB', 'STOCK_4X9_LEADING_DOC_TAB'),
    ('STOCK_4X9_TRAILING_DOC_TAB', 'STOCK_4X9_TRAILING_DOC_TAB'),
    ('STOCK_4X85_TRAILING_DOC_TAB', 'STOCK_4X85_TRAILING_DOC_TAB'),
    ('STOCK_4X105_TRAILING_DOC_TAB', 'STOCK_4X105_TRAILING_DOC_TAB'),
]

HELP_EXTRA_DATA = """The extra data in FedEx is organized like the inside of a json file.
This functionality is advanced/technical and should only be used if you know what you are doing.
More info on https://www.developer.fedex.com"""


class ProviderFedex(models.Model):
    _inherit = 'delivery.carrier'
    prod_environment = fields.Boolean(string="Environment", compute="_compute_prod_environment", store=True)
    support_test_environment = fields.Boolean(string="Test Environment", compute="_compute_support_test_environment")
    delivery_type = fields.Selection(selection_add=[
        ('fedex_certified', "FedEx"),
    ], ondelete={'fedex_certified': lambda recs: recs.write({'delivery_type': 'fixed', 'fixed_price': 0})})

    fedex_certified_account_id = fields.Many2one('fedex.certified.account', string="FedEx Certified Account", groups="base.group_system", compute="_compute_fedex_certified_account_id", readonly=False, store=True,
                                                domain="['|', ('company_ids', 'in', [company_id]), ('company_ids', '=', False), ('test_account', '!=', prod_environment)] if company_id else [('company_ids', '=', False), ('test_account', '!=', prod_environment)]")
    fedex_certified_account_number = fields.Char(related='fedex_certified_account_id.account_number', string="Account Number", readonly=True)
    fedex_certified_test_country_code = fields.Selection([
        ('ZA', 'South Africa'),
    ], string="Test Country")
    fedex_certified_droppoff_type = fields.Selection([('CONTACT_FEDEX_TO_SCHEDULE', 'Contact FedEx for pickup'),
                                                 ('DROPOFF_AT_FEDEX_LOCATION', 'Drop off at FedEx location'),
                                                 ('USE_SCHEDULED_PICKUP', 'Part of regular scheduled pickup')],
                                                string="FedEx Certified - Drop-Off Type",
                                                default='USE_SCHEDULED_PICKUP')
    fedex_certified_default_package_type_id = fields.Many2one('stock.package.type', string="FedEx Certified - Package Type")
    fedex_certified_service_type = fields.Selection([
        # ('FEDEX_1_DAY_FREIGHT', 'FedEx 1Day® Freight'),
        ('FEDEX_2_DAY', 'FedEx 2Day®'),
        ('FEDEX_2_DAY_AM', 'FedEx 2Day® AM'),
        # ('FEDEX_2_DAY_FREIGHT', 'FedEx 2Day® Freight'),
        # ('FEDEX_3_DAY_FREIGHT', 'FedEx 3Day® Freight'),
        ('FEDEX_ECONOMY', 'FedEx Economy'),
        # ('FEDEX_ECONOMY_FREIGHT', 'FedEx Economy Freight'),
        ('FEDEX_ECONOMY_SELECT', 'FedEx Economy (Only U.K.)'),
        ('FEDEX_EXPRESS_SAVER', 'FedEx Express Saver®'),
        ('FEDEX_FIRST', 'FedEx First'),
        # ('FEDEX_FIRST_FREIGHT', 'FedEx First Overnight® Freight'),
        ('FEDEX_GROUND', 'FedEx International Ground® and FedEx Domestic Ground®'),
        ('FEDEX_INTERNATIONAL_CONNECT_PLUS', 'FedEx International Connect Plus®'),
        # ('FEDEX_INTERNATIONAL_DEFERRED_FREIGHT', 'FedEx® International Deferred Freight'),
        ('FEDEX_INTERNATIONAL_PRIORITY', 'FedEx International Priority®'),
        ('FEDEX_INTERNATIONAL_PRIORITY_EXPRESS', 'FedEx International Priority® Express'),
        ('FEDEX_PRIORITY', 'FedEx Priority'),
        ('FEDEX_PRIORITY_EXPRESS', 'FedEx Priority Express'),
        # ('FEDEX_PRIORITY_EXPRESS_FREIGHT', 'FedEx Priority Express Freight'),
        # ('FEDEX_PRIORITY_FREIGHT', 'FedEx Priority Freight'),
        ('FEDEX_REGIONAL_ECONOMY', 'FedEx® Regional Economy'),
        # ('FEDEX_REGIONAL_ECONOMY_FREIGHT', 'FedEx® Regional Economy Freight'),
        ('FIRST_OVERNIGHT', 'FedEx First Overnight®'),
        ('GROUND_HOME_DELIVERY', 'FedEx Home Delivery®'),
        # ('INTERNATIONAL_DISTRIBUTION_FREIGHT', 'FedEx International Priority DirectDistribution® Freight'),
        ('INTERNATIONAL_ECONOMY', 'FedEx® International Economy'),
        # ('INTERNATIONAL_ECONOMY_DISTRIBUTION', 'FedEx International Economy DirectDistribution'),
        # ('INTERNATIONAL_ECONOMY_FREIGHT', 'FedEx International Economy® Freight'),
        ('INTERNATIONAL_FIRST', 'FedEx International First®'),
        # ('INTERNATIONAL_PRIORITY_DISTRIBUTION', 'FedEx International Priority DirectDistribution®'),
        # ('INTERNATIONAL_PRIORITY_FREIGHT', 'FedEx International Priority® Freight'),
        # ('INTL_GROUND_DISTRIBUTION', 'International Ground® Distribution (IGD)'),
        ('PRIORITY_OVERNIGHT', 'FedEx Priority Overnight®'),
        ('SAME_DAY', 'FedEx SameDay®'),
        ('SAME_DAY_CITY', 'FedEx SameDay® City'),
        ('SMART_POST', 'FedEx Ground® Economy'),
        ('STANDARD_OVERNIGHT', 'FedEx Standard Overnight®'),
        ('TRANSBORDER_DISTRIBUTION', 'Transborder distribution'),
    ], default='FEDEX_INTERNATIONAL_PRIORITY', string='FedEx Certified Service Type')
    fedex_certified_duty_payment = fields.Selection([('SENDER', 'Sender'), ('RECIPIENT', 'Recipient')], required=True, default="SENDER")
    fedex_certified_weight_unit = fields.Selection([('LB', 'Pounds'), ('KG', 'Kilograms')], default='LB')
    fedex_certified_label_stock_type = fields.Selection(FEDEX_STOCK_TYPE, string='FedEx Label Size', default='PAPER_LETTER')
    fedex_certified_label_file_type = fields.Selection([('PDF', 'PDF'),
                                                   ('EPL2', 'EPL2'),
                                                   ('PNG', 'PNG'),
                                                   ('ZPLII', 'ZPLII')],
                                                  default='PDF', string="FedEx Certified - Label File Type")

    fedex_certified_extra_options = fields.Char("Extra Options")

    fedex_certified_extra_data_rate_request = fields.Text('FedEx Certified - Extra data for rate', help=HELP_EXTRA_DATA)
    fedex_certified_extra_data_ship_request = fields.Text('FedEx Certified - Extra data for ship', help=HELP_EXTRA_DATA)
    fedex_certified_extra_data_return_request = fields.Text('FedEx Certified - Extra data for return', help=HELP_EXTRA_DATA)

    fedex_certified_override_shipper_vat = fields.Char('FedEx Certified - Union tax id (EORI/IOSS)', help='Will be provided to Fedex as primary company tax identifier of type BUSINESS_UNION to put on the generated invoice. Use this when you need to use an IOSS or EORI number in addition to the national tax number. When not provided the regular tax id on the company will be used with type BUSINESS_NATIONAL.')
    fedex_certified_email_notifications = fields.Boolean('FedEx Certified - Email Notifications', help='When enabled, the customer will receive email notifications from FedEx about this shipment (when an email address is configured on the customer)')
    fedex_certified_documentation_type = fields.Selection(
        [('none', 'No'), ('invoice', 'Print PDF'), ('etd', 'Electronic Trade Documents')], 'Fedex Certified - Generate invoice', default="none", required=True,
                help='For international shipments (or some intra-country shipments), a commercial invoice might be required for customs clearance. This commercial invoice can be generated by FedEx based on shipment data and returned as PDF for printing and attaching to the shipment or manual electronic submission to FedEx. It can also be submitted directly as ETD information to FedEx upon shipment validation.')
    fedex_certified_residential_address = fields.Selection(
        [('never', 'Never'), ('always', 'Always'), ('check', 'Check using FedEx Address API')],
        'FedEx Certified - Residential delivery', default='never', required=True,
        help='Determines whether to mark the recipient address as residential (to correctly calculate any possible surcharges). Please note: when retrieving this information using the FedEx Address API, we assume that the address is residential unless it is marked explicitly as a BUSINESS address.')

    @api.depends("delivery_type")
    def _compute_support_test_environment(self):
        for carrier in self:
            carrier.support_test_environment = carrier.delivery_type not in ['fixed', 'base_on_rule', 'fedex_certified']

    @api.depends("support_test_environment")
    def _compute_prod_environment(self):
        for carrier in self:
            carrier.prod_environment = not carrier.support_test_environment

    @api.depends("prod_environment")
    def _compute_fedex_certified_account_id(self):
        for carrier in self:
            carrier.fedex_certified_account_id = False

    def _compute_can_generate_return(self):
        super()._compute_can_generate_return()
        for carrier in self:
            if carrier.delivery_type == 'fedex_certified':
                carrier.can_generate_return = True

    def _compute_supports_shipping_insurance(self):
        super()._compute_supports_shipping_insurance()
        for carrier in self:
            if carrier.delivery_type == 'fedex_certified':
                carrier.supports_shipping_insurance = True

    def action_open_account_registration_wizard(self):
        # https://www.fedex.com/content/dam/fedex-com/hdn/FedEx_End_User_License_Agreement_Distributed_Technology.pdf
        # Show EULA at first
        self.ensure_one()
        wizard = self.env['fedex.certified.account.registration.wizard'].create({
            'company_id': self.company_id.id,
            'fedex_carrier_id': self.id,
        })
        return {
            'name': 'FedEx Account Registration',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'fedex.certified.account.registration.wizard',
            'res_id': wizard.id,
            'views': [[self.env.ref('delivery_fedex_certified.view_fedex_account_registration_eula_form').id, 'form']],
            'context': self.env.context,
        }

    def fedex_certified_rate_shipment(self, order):
        srm = FedexRequest(self)
        try:
            response = srm._get_shipping_price(
                ship_from=order.warehouse_id.partner_id,
                ship_to=order.partner_shipping_id,
                packages=self._get_packages_from_order(order, self.fedex_certified_default_package_type_id),
                currency=order.currency_id.name
            )
        except ValidationError as err:
            return {'success': False,
                    'price': 0.0,
                    'error_message': _('Error(s) from FedEx:\n%s', err),
                    'warning_message': False}

        warnings = response.get('alert_message')
        if warnings:
            _logger.info(warnings)

        return {'success': True,
                'price': response.get('price'),
                'error_message': False,
                'warning_message': _('Warning(s) from FedEx:\n%s', warnings) if warnings else False}

    def fedex_certified_send_shipping(self, pickings):
        res = []
        srm = FedexRequest(self)
        for picking in pickings:
            packages = self._get_packages_from_picking(picking, self.fedex_certified_default_package_type_id)
            response = srm._ship_package(
                ship_from_wh=picking.picking_type_id.warehouse_id.partner_id,
                ship_from_company=picking.company_id.partner_id,
                ship_to=picking.partner_id,
                sold_to=picking.sale_id.partner_invoice_id,
                packages=packages,
                currency=picking.sale_id.currency_id.name or picking.company_id.currency_id.name,
                order_no=picking.sale_id.name,
                customer_ref=picking.sale_id.client_order_ref,
                picking_no=picking.name,
                incoterms=picking.sale_id.incoterm.code,
                freight_charge=picking.sale_id.order_line.filtered(lambda sol: sol.is_delivery and sol.product_id == self.product_id).price_total,
            )

            warnings = response.get('alert_message')
            if warnings:
                _logger.info(warnings)

            logmessage = Markup("%s<br/>%s<br/><b>%s</b> %s<br/><b>%s</b> %s") % (_("Shipment created into FedEx"), response.get('service_info', ''), _("Tracking Numbers:"), response.get('tracking_numbers', ''), _("Packages:"), ','.join([p.name for p in packages if p.name]))
            if response.get('documents'):
                logmessage += Markup("<br/><b>%s</b> %s") % (_("Required documents:"), response.get('documents'))

            # `response['attachments']` is the flat list of every encoded
            # document FedEx attached to the shipment — per-piece (LABEL,
            # AUXILIARY, customs slips, …) AND shipment-level
            # (COMMERCIAL_INVOICE, PRO_FORMA_INVOICE, …). The connector now
            # decodes and names them all in one pass; the older
            # response['labels'] / response['invoice'] keys are still
            # populated for backward compatibility but contain only a subset.
            attachments = list(response.get('attachments') or [])

            lognote_pickings = picking
            if picking.sale_id:
                lognote_pickings |= picking.sale_id.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))

            for pick in lognote_pickings:
                pick.message_post(body=logmessage, attachments=attachments)

            res.append({'exact_price': response.get('price'), 'tracking_number': response.get('tracking_numbers')})

            if self.return_label_on_delivery:
                if len(packages) > 1:
                    picking.message_post(body=_("Automated return label generation is not supported by FedEx for multi-package shipments. Please generate the return labels manually."))
                else:
                    self.get_return_label(picking, tracking_number=response.get('tracking_numbers').split(',')[0], origin_date=response.get('date'))

        return res

    def fedex_certified_get_return_label(self, picking, tracking_number=None, origin_date=None):
        srm = FedexRequest(self)
        response = srm._return_package(
            ship_from=picking.partner_id,
            ship_to_company=picking.company_id.partner_id,
            ship_to_wh=picking.picking_type_id.warehouse_id.partner_id,
            packages=self._get_packages_from_picking(picking, self.fedex_certified_default_package_type_id),
            currency=picking.sale_id.currency_id.name or picking.company_id.currency_id.name,
            tracking=tracking_number,
            date=origin_date
        )

        warnings = response.get('alert_message')
        if warnings:
            _logger.info(warnings)

        logmessage = Markup("%s<br/><b>%s</b> %s<br/>") % (_("Return Label"), _("Tracking Numbers:"), response.get('tracking_numbers'))
        if response.get('documents'):
            logmessage += Markup("<b>%s</b> %s") % (_("Required documents:"), response.get('documents'))

        # Same as fedex_certified_send_shipping above — log every document the
        # return call produces (LABEL + AUXILIARY + any customs slips), not
        # just the first LABEL per piece.
        fedex_labels = list(response.get('attachments') or [])
        picking.message_post(body=logmessage, attachments=fedex_labels)

    def fedex_certified_get_tracking_link(self, picking):
        return 'https://www.fedex.com/wtrk/track/?' + urlencode({"trknbr": picking.carrier_tracking_ref})

    def fedex_certified_cancel_shipment(self, picking):
        master_tracking = picking.carrier_tracking_ref.split(',')[0]
        request = FedexRequest(self)
        result = request.cancel_shipment(master_tracking)

        warnings = result.get('warnings_message')
        if warnings:
            _logger.info(warnings)

        if result.get('delete_success') and not result.get('errors_message'):
            picking.message_post(body=_('Shipment %s has been cancelled', picking.carrier_tracking_ref))
            picking.write({'carrier_tracking_ref': '', 'carrier_price': 0.0})
        else:
            raise UserError(result['errors_message'])

    def _fedex_certified_convert_weight(self, weight):
        if self.fedex_certified_weight_unit == 'KG':
            convert_to = 'uom.product_uom_kgm'
        elif self.fedex_certified_weight_unit == 'LB':
            convert_to = 'uom.product_uom_lb'
        else:
            raise ValueError

        weight_uom_id = self.env['product.template']._get_weight_uom_id_from_ir_config_parameter()
        new_value = weight_uom_id._compute_quantity(weight, self.env.ref(convert_to), round=False)

        # Some users may want to ship very lightweight items; in order to give them a rating, we round the
        # converted weight of the shipping to the smallest value accepted by FedEx: 0.01 kg or lb.
        # (in the case where the weight is actually 0.0 because weights are not set, don't do this)
        if weight > 0.0:
            new_value = max(new_value, 0.01)

        # Rounding to avoid differences between sum of values before and after conversion, caused by
        # Floating Point Arithmetic issues (ex: .1 + .1 + .1 != .3)
        return float_repr(new_value, 10)
