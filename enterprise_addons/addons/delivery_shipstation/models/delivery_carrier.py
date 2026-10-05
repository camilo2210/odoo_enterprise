# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
import time

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.delivery_shipstation.models.shipstation_request import ShipStation


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(
        selection_add=[('shipstation', 'ShipStation')],
        ondelete={'shipstation': lambda recs: recs.write({'delivery_type': 'fixed', 'fixed_price': 0})},
    )

    shipstation_production_api_key = fields.Char(
        string="ShipStation V2 API Production Token",
        help="To integrate, generate a Production V2 API Key within your ShipStation dashboard. Note: V1 keys are not supported for this implementation.",
        copy=False, groups="base.group_system",
    )

    shipstation_default_package_type_id = fields.Many2one(
        comodel_name="stock.package.type",
        string="ShipStation Default Package",
        domain="[('package_carrier_type', '=', 'shipstation'), ('shipstation_carrier_code', 'in', [False, shipstation_carrier_code])]",
        help="Default package type for ShipStation",
    )

    shipstation_carrier_code = fields.Char(
        string="ShipStation Carrier Code",
        copy=False,
        help="The carrier on ShipStation used by this carrier. The service code belongs to it.",
    )

    shipstation_service_code = fields.Char(
        string="ShipStation Service Code",
        copy=False,
        help="The service that will be used for this carrier. This is set when you select a carrier from the wizard.",
    )

    shipstation_service_name = fields.Char(
        string="ShipStation Service Name",
        copy=False,
        help="The service that will be used for this carrier. This is set when you select a carrier from the wizard.",
    )

    shipstation_label_layout = fields.Selection(
        selection=[
            ("4x6", "4x6"),
            ("letter", "Letter"),
        ],
        string="ShipStation Label Layout",
        help="Available layouts (sizes) in which shipping labels can be downloaded.",
        default='letter',
    )

    shipstation_label_file_type = fields.Selection(
        selection=[
            ('PNG', 'PNG'),
            ('PDF', 'PDF'),
            ('ZPL', 'ZPL'),
        ],
        string="ShipStation Label Format",
        help="Possible file formats in which shipping labels can be downloaded. We recommend PDF format because it is supported by all carriers.",
        default='PDF',
    )

    shipstation_insurance_provider = fields.Selection(
        selection=[
            ('parcelguard', 'ParcelGuard'),
            ('carrier', 'Carrier-Provided Insurance'),
            ('third_party', 'External Insurance'),
        ],
        string="ShipStation Insurance Provider",
        help="Indicates a preferred insurance provider for your shipment.",
    )

    shipstation_confirmation_type = fields.Selection(
        selection=[
            ('delivery', 'Delivery'),
            ('signature', 'Signature'),
            ('adult_signature', 'Adult Signature'),
            ('verbal_confirmation', 'Verbal Confirmation'),
            ('age_verification_16_plus', 'Age Verification 16+'),
        ],
        string="ShipStation Confirmation",
        help="Indicates the type of delivery confirmation you want for your shipment. The available options depend on the carrier and service you choose.",
    )

    shipstation_additional_handling = fields.Boolean(string="Requires Additional Handling", default=False)

    # Readonly values as they come directly from the API not set in Odoo
    shipstation_supports_multipackage = fields.Boolean(string="Support Multi-Package", default=False, readonly=True, copy=False)
    shipstation_supports_returns = fields.Boolean(string="Support Returns", default=False, readonly=True, copy=False)

    @api.constrains('shipstation_label_layout', 'shipstation_label_file_type')
    def _check_label_configuration(self):
        for record in self:
            if record.delivery_type == 'shipstation' and record.shipstation_label_file_type != 'PDF' and record.shipstation_label_layout == 'letter':
                raise ValidationError(record.env._("The 'Letter' layout is only compatible with the PDF format. Please choose a different combination."))

    def _compute_supports_shipping_insurance(self):
        super()._compute_supports_shipping_insurance()
        for carrier in self:
            if carrier.delivery_type == 'shipstation':
                carrier.supports_shipping_insurance = True

    @api.depends('shipstation_supports_returns')
    def _compute_can_generate_return(self):
        super()._compute_can_generate_return()
        for carrier in self:
            if carrier.delivery_type == 'shipstation' and carrier.shipstation_supports_returns:
                carrier.can_generate_return = True

    def action_open_shipstation_wizard(self):
        """ Fetch carriers and channels from ShipStation account.
        Create record(s) of carriers(s) in Odoo.
        """
        self.ensure_one()
        if self.delivery_type != 'shipstation':
            raise ValidationError(self.env._('This action requires a ShipStation carrier.'))

        shipstation = ShipStation(self, self.log_xml)
        carriers_data = shipstation._fetch_shipstation_carriers()

        if errors_found := carriers_data.get('error'):
            raise ValidationError(errors_found)
        carriers_list = carriers_data.get('carriers')
        if not carriers_list:
            raise ValidationError(self.env._("Failed to fetch ShipStation Carriers, Please try again later."))
        return {
            'type': 'ir.actions.client',
            'tag': 'shipstation_carrier_selector',
            'target': 'new',
            'params': {
                'carrier_record_id': self.id,
                'carriers': carriers_list,
                'current_carrier_id': self.shipstation_carrier_code,
                'current_service_code': self.shipstation_service_code,
            },
        }

    def update_shipstation_config(self, carrier_id, service_code, service_name, packages, is_multi_package_supported, is_return_supported):
        """ The return call from the action opened in action_open_shipstation_wizard
        It will set the correct values based on what's appeared in the popup.
        """
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(self.env._("Only system administrators can sync ShipStation carriers."))
        self.check_access('write')
        vals = {
            'shipstation_carrier_code': carrier_id,
            'shipstation_service_code': service_code,
            'shipstation_service_name': service_name,
            'shipstation_supports_multipackage': is_multi_package_supported,
            'shipstation_supports_returns': is_return_supported,
            'return_label_on_delivery': False,  # Reset to false in case the new provider doesn't support it.
            'get_return_label_from_portal': False,
        }
        # Drop a default package tied to a different carrier: its carrier-scoped
        # code would otherwise be sent with the newly selected carrier and rejected.
        old_default = self.shipstation_default_package_type_id
        if old_default.shipstation_carrier_code and old_default.shipstation_carrier_code != carrier_id:
            vals['shipstation_default_package_type_id'] = False
        self.write(vals)
        if packages:
            already_existing_packages = self.env['stock.package.type'].search_read([
                ('package_carrier_type', '=', 'shipstation'),
                ('shipstation_carrier_code', 'in', [carrier_id, False]),
                ('shipper_package_code', 'in', [package['package_code'] for package in packages]),
            ], ['shipper_package_code'])
            existing_codes = {package['shipper_package_code'] for package in already_existing_packages}

            new_packages = [package for package in packages if package['package_code'] not in existing_codes]

            self.env['stock.package.type'].create([{
                'name': package['name'],
                'package_carrier_type': 'shipstation',
                'shipper_package_code': package['package_code'],
                'shipstation_carrier_code': carrier_id,
            } for package in new_packages])

    def shipstation_rate_shipment(self, order):
        """ Returns shipping rate for the order and chosen delivery method."""
        if not self.shipstation_carrier_code or not self.shipstation_service_code:
            return {
                'success': False,
                'price': 0.0,
                'error_message': self.env._(
                    "No carrier is set on \"%(delivery_method)s\". To use ShipStation, you'll need to sync your carriers with your account.",
                    delivery_method=self.name,
                ),
                'warning_message': False,
            }

        order_weight = self.env.context.get('order_weight', None)
        carrier = self
        if order_weight:
            # The rate wizard's order_weight is just the product weight; pre-bake the
            # default package's base_weight (tare) into the context so the base
            # _get_packages_from_order produces a per-package weight that includes it.
            carrier = self.with_context(order_weight=order_weight + self.shipstation_default_package_type_id.base_weight)
        shipstation = ShipStation(carrier, self.log_xml)
        try:
            result = shipstation._rate_request(order)
        except UserError as e:
            return {
                'success': False,
                'price': 0.0,
                'error_message': e.args[0] if e.args else str(e),
                'warning_message': False,
            }

        if result.get('error_found'):
            return {
                'success': False,
                'price': 0.0,
                'error_message': result['error_found'],
                'warning_message': False,
            }

        price = float(result['price'])
        return {
            'success': True,
            'price': price,
            'error_message': False,
            'warning_message': result.get('warning_message'),
        }

    def shipstation_send_shipping(self, pickings):
        """ Send shipment to ShipStation for validation.
        Creates shipment and generates/buys label.
        """
        if not self.shipstation_carrier_code or not self.shipstation_service_code:
            raise UserError(self.env._(
                "No carrier is set on \"%(delivery_method)s\". To use ShipStation, you'll need to sync your carriers with your account.",
                delivery_method=self.name,
            ))
        res = []
        shipstation = ShipStation(self, self.log_xml)
        for picking in pickings:
            company_warehouse = picking.picking_type_id.warehouse_id
            recipient = picking.partner_id
            shipper = company_warehouse.partner_id or company_warehouse.company_id.partner_id
            shipment = shipstation._send_shipping(recipient, shipper, picking)
            picking.shipstation_label_ref = shipment.get('label_ids')
            res.append({
                'tracking_number': shipment.get('tracking_number'),
                'exact_price': shipment.get('exact_price'),
            })
            # generate return if config is set. Only in production: in test mode
            # the return label is still bought with the production key and its id
            # is discarded, leaving an unvoidable live label on the account.
            if self.prod_environment and picking.carrier_id.return_label_on_delivery:
                if recipient.country_id != shipper.country_id:
                    picking.message_post(body=self.env._("Return label generation is only supported for domestic shipments. Skipping."))
                else:
                    try:
                        self.get_return_label(picking)
                    except UserError:
                        # if the return fails need to log that they failed and continue
                        picking.message_post(body=self.env._('Failed to create the return label!'))

            if not self.prod_environment:
                picking.message_post(body=self.env._("Automatically cancelling ShipStation shipment as the carrier is not in Production Mode."))
                # Need carrier_tracking_ref to cancel shipment
                picking.carrier_tracking_ref = shipment.get('tracking_number')
                self.shipstation_cancel_shipment(picking)
                # If the auto-cancel succeeded, drop the tracking number from the result
                # so the upstream send_to_shipper doesn't write it back onto the picking.
                if not picking.carrier_tracking_ref:
                    res[-1]['tracking_number'] = False
                    # The label was voided; zero the price too, otherwise base
                    # send_to_shipper re-applies it as carrier_price and invoices it.
                    res[-1]['exact_price'] = 0.0
        return res

    def shipstation_get_return_label(self, picking, tracking_number=None, origin_date=None):
        """ Return a shipment to ShipStation.
        Creates a return shipment and generates/buys label.
        """
        if not self.shipstation_carrier_code or not self.shipstation_service_code:
            raise UserError(self.env._(
                "No carrier is set on \"%(delivery_method)s\". To use ShipStation, you'll need to sync your carriers with your account.",
                delivery_method=self.name,
            ))
        shipstation = ShipStation(self, self.log_xml)
        origin_picking = picking
        if picking.is_return_picking:
            # A real return picking carries no label ref of its own; the original
            # outgoing delivery holds the label the return is built from.
            origin_picking = picking.move_ids.origin_returned_move_id.picking_id[:1]
        shipment = shipstation._return_shipment(origin_picking, log_picking=picking)
        if picking.is_return_picking:
            picking.shipstation_label_ref = shipment.get('label_ids')

    def shipstation_cancel_shipment(self, pickings):
        """ Cancel shipment in ShipStation."""
        shipstation = ShipStation(self, self.log_xml)
        for picking in pickings:
            if picking.carrier_id.delivery_type != 'shipstation' or not picking.carrier_tracking_ref:
                picking.message_post(body=self.env._("ShipStation order(s) not found to cancel shipment!"))
                continue
            # ShipStation is eventually consistent: a void right after label creation may
            # hit a server that hasn't seen the label yet, so retry once before reporting.
            warnings = shipstation._cancel_shipment(picking)
            if warnings:
                time.sleep(1.5)
                warnings = shipstation._cancel_shipment(picking)

            failed_label_refs = set()
            failed_trackings = set()

            warning_messages = []
            for failed_label, warning in warnings.items():
                failed_label_refs.add(failed_label)
                failed_trackings.add(warning['tracking_number'])
                if warning['message']:
                    warning_messages.append(
                        Markup("<li>{warning_message}</li>").format(
                            warning_message=warning['message'],
                        ),
                    )

            if warnings:
                message = Markup().join(warning_messages)
                logmessage = Markup("""
                    <p>{header}</p>
                    <ul>{warnings_messages}</ul>
                """).format(
                    header=self.env._(
                        "Unable to cancel the following tracking number(s) %(tracking_numbers)s due to warnings below:",
                        tracking_numbers=failed_trackings,
                    ),
                    warnings_messages=message,
                )
                picking.message_post(body=logmessage)

            picking.write({
                "shipstation_label_ref": ','.join(failed_label_refs) if failed_label_refs else False,
                "carrier_tracking_ref": ','.join(failed_trackings) if failed_trackings else False,
                "carrier_price": 0.00 if not failed_trackings else picking.carrier_price,
            })

    def shipstation_get_tracking_link(self, picking):
        """ Get tracking link for the picking."""
        if not picking.carrier_tracking_ref:
            return False
        shipstation = ShipStation(self, self.log_xml)
        tracking_urls = set()
        tracking_numbers = picking.carrier_tracking_ref
        for tracking_number in tracking_numbers.split(','):
            label = shipstation._get_label_from_tracking_number(tracking_number)
            if not label:
                continue
            tracking_urls.add((str(tracking_number), label.get('tracking_url')))
        tracking_urls = list(tracking_urls)
        return (len(tracking_urls) == 1 and tracking_urls[0][1]) or json.dumps(tracking_urls)
