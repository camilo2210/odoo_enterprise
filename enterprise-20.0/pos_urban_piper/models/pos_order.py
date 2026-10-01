# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta, timezone
from markupsafe import Markup

import json
import random
import string

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

from ..utils.schema_validation import ORDER_STATUS_MAPPING
from ..utils.urbanpiper_connector import UrbanPiperConnector


class PosOrder(models.Model):
    _inherit = 'pos.order'

    source = fields.Selection(selection_add=[
        ('online', 'Online Food Delivery')
    ])
    delivery_status = fields.Selection([
        ('placed', 'Placed'),
        ('acknowledged', 'Acknowledged'),
        ('food_ready', 'Food Ready'),
        ('dispatched', 'Dispatched'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')], string='Delivery Status', tracking=True, readonly=True, help='Status of the order as provided by UrbanPiper.')
    delivery_provider_id = fields.Many2one(
        'pos.delivery.provider',
        string='Delivery Provider',
        tracking=True,
        readonly=True,
        help='Responsible delivery provider for online order, e.g., UberEats, Zomato.'
    )
    delivery_identifier = fields.Char(string='Delivery ID', tracking=True, readonly=True, help='Unique delivery ID provided by UrbanPiper.')
    delivery_json = fields.Json(string='Delivery JSON', readonly=True, help='JSON data of the order.', store=True)
    delivery_rider_json = fields.Json(string='Delivery Rider JSON', readonly=True, help='JSON data of the delivery rider.', store=True)
    prep_time = fields.Integer(
        string='Food Preparation Time',
        help='Preparation time for the food as provided by UrbanPiper.'
    )
    preparation_time = fields.Float(
        string='Taken Preparation Time',
        help='Actual preparation time taken for the food to prepare.'
    )
    urbanpiper_printed = fields.Boolean(string='UrbanPiper Preparation Ticket Printed')

    def _cron_process_pos_orders(self):
        super()._cron_process_pos_orders()
        self.notify_future_deliveries()

    @api.model
    def notify_future_deliveries(self):
        """
        Notify POS about upcoming delivery orders once they reach their
        preparation window, and cancel orders if the store is closed.
        """
        utcnow = datetime.utcnow()
        future_orders = self.search([
            ('state', '=', 'draft'),
            ('source', '=', 'online'),
            ('preset_time', '>', utcnow),
            ('urbanpiper_printed', '=', False),
        ])
        orders_to_notify = {}
        for order in future_orders:
            if utcnow < order.preset_time - timedelta(minutes=order.prep_time):
                continue
            if not order.config_id.current_session_id:
                order.order_status_update(order.id, 'Cancelled', 'store_closed')
                order.state = 'cancel'
                continue
            if order.session_id != order.config_id.current_session_id:
                order.session_id = order.config_id.current_session_id
            orders_to_notify.setdefault(order.config_id, []).append(order.id)
        for config, order_ids in orders_to_notify.items():
            config._notify('FUTURE_ORDER_NOTIFICATION', order_ids)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_online_order(self):
        if (self.filtered(lambda o: o.delivery_identifier)):
            raise UserError(_('Online orders cannot be deleted. If needed, reject the order instead or contact the food delivery provider.'))

    @api.model
    def _load_pos_preparation_data_fields(self):
        res = super()._load_pos_preparation_data_fields()
        return res + ['delivery_status', 'delivery_provider_id', 'delivery_identifier', 'prep_time', 'delivery_json']

    def mark_urbanpiper_prep_order_as_printed(self):
        self.ensure_one()
        # Lock the line
        self.env.cr.execute(
            'SELECT id FROM pos_order WHERE id = %s FOR UPDATE NOWAIT',
            (self.id,)
        )

        if self.urbanpiper_printed:
            raise UserError(self.env._("This delivery order has already been printed automatically."))

        self.urbanpiper_printed = True
        return True

    def _get_line_tax_liability(self, taxes_data):
        """Determine which entity is liable for taxes on this order line."""
        return 'aggregator' if any(
            tax.get('liability_on') == 'aggregator'
            for tax in (taxes_data or [])
        ) else 'merchant'

    def _reframe_notes(self, notes):
        """
        Convert newline-separated notes into a JSON payload for POS orders and order lines.
        NOTE: `pos.note` is not searched since online order notes rarely match POS notes.
        """
        notes_array = []
        for note_name in notes.split('\n'):
            if note_name := note_name.strip():
                notes_array.append({
                    'text': note_name,
                    'colorIndex': random.randint(0, 11),
                })
        return json.dumps(notes_array)

    @api.model
    def process_urbanpiper_order_placed(self, data, urbanpiper_store):
        """
        # UrbanPiper Webhook Handler
        Process and create an UrbanPiper order from webhook data.

        Validates the incoming payload and creates a new order if all
        required references—order details, configuration, and provider—are present.
        Also attaches related order lines derived from items, charges, and
        discount information included in the payload.

        Doc: https://api-docs.urbanpiper.com/downstream/api/endpoints/order-management/order-relay
        :param data: Dictionary containing the raw order data to be processed.
        :type data: dict
        """
        order_data = data['order']
        order_details = order_data['details']
        prep_time_data = order_details.get('prep_time', {})
        discounts_data = order_details.get('ext_platforms', [{}])[0].get('discounts', [])
        log_urbanpiper = self.env['pos.config'].log_urbanpiper

        if self.search_count([('delivery_identifier', '=', order_details['id'])], limit=1):
            log_urbanpiper(f"UrbanPiper: Order {order_details['id']} already exists.", 'UrbanPiper Order already exists', func='process_urbanpiper_order_placed')
            return False

        pos_config = urbanpiper_store.config_id
        if not pos_config.current_session_id:
            log_urbanpiper(
                f"UrbanPiper: Store or session not found for ID: {order_data['store']['merchant_ref_id']}.",
                'UrbanPiper PoS Config or Active Session Not Found',
                func='process_urbanpiper_order_placed'
            )
            return False

        if not (pos_delivery_provider := self.env['pos.delivery.provider'].search([('technical_name', '=', order_details['channel'])], limit=1)):
            log_urbanpiper(
                f"UrbanPiper: Delivery provider - {order_details['channel']} not found",
                'UrbanPiper Delivery Provider Not Found',
                func='process_urbanpiper_order_placed'
            )
            return False

        lines = [
            line
            for line_data in order_data['items']
            if (line := self._process_urbanpiper_order_line(line_data, urbanpiper_store))
        ]
        self._process_urbanpiper_charges(order_details.get('charges', []), lines, urbanpiper_store)
        # shows aggregator discount info in general_note
        general_note = '\n'.join([
            _("Aggregator Discount: %(currency)s %(value)s", currency=pos_config.currency_id.symbol, value=discount.get('value'))
            for discount in discounts_data if not discount.get('is_merchant_discount')
        ])
        pos_reference, tracking_number = pos_config._get_next_order_refs()
        aggregator = urbanpiper_store.aggregator_lines.filtered_domain([('delivery_provider_id', '=', pos_delivery_provider.id)])
        store_preset = urbanpiper_store.preset_id
        pos_order = self.create({
            'partner_id': aggregator._get_order_customer(data['customer']).id,
            'pos_reference': pos_reference,
            'tracking_number': tracking_number,
            'config_id': pos_config.id,
            'session_id': pos_config.current_session_id.id,
            'company_id': pos_config.company_id.id,
            'fiscal_position_id': store_preset.fiscal_position_id.id,
            'lines': lines,
            'amount_paid': 0.0,  # calculation is done below
            'amount_total': 0.0,
            'amount_tax': 0.0,
            'amount_return': 0.0,
            'delivery_identifier': order_details['id'],
            'delivery_status': order_details['order_state'].lower(),
            'general_customer_note': '\n'.join(
                x for x in [order_details.get('instructions'), general_note] if x and x.strip()
            ),
            'delivery_provider_id': pos_delivery_provider.id,
            'prep_time': int(prep_time_data.get('estimated') or prep_time_data.get('max')) or 0,
            'delivery_json': json.dumps(data),
            'user_id': pos_config.current_session_id.user_id.id,
            'source': 'online',
            'preset_id': store_preset.id,
            'ticket_code': ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
        })
        pos_order._process_urbanpiper_discounts(discounts_data)
        pos_order._compute_prices()
        # Future delivery orders
        delivery_timestamp = order_details.get('delivery_datetime')
        created_timestamp = order_details.get('created')
        if int((delivery_timestamp - created_timestamp) / (1000 * 60)) > pos_order.prep_time:
            pos_order.preset_time = datetime.fromtimestamp(
                delivery_timestamp / 1000.0, timezone.utc
            ).replace(tzinfo=None)
        pos_order.config_id._notify_delivery_order(pos_order.id)
        return pos_order

    def _get_urbanpiper_product_variant(self, options_data, product_tmpl_id):
        """
        Compute the product variant from UrbanPiper option data and create it if needed.
        Also computes extra price and option notes.
        """
        note, attr_value_ids, price_extra = '', [], 0
        for option in options_data:
            attr_value_id = int(option.get('merchant_id').split('-')[1])
            if int(option.get('quantity', 0)) > 1:
                # to show multiple qty options info, currentlly not supported in pos
                note = '\n'.join([note, f"{option.get('title')} X {option.get('quantity')}"])
            price_extra += option.get('total_price', 0)
            attr_value_ids.append(attr_value_id)
        ptav_ids = self.env['product.template.attribute.value']
        if attr_value_ids:
            ptav_ids = self.env['product.template.attribute.value'].search([
                ('product_tmpl_id', '=', product_tmpl_id),
                ('product_attribute_value_id', 'in', attr_value_ids),
                ('ptav_active', '=', True),
            ])

        products = self.env['product.product'].search([('product_tmpl_id', '=', product_tmpl_id)])
        variant_value_ids = sorted(ptav_ids.filtered(lambda l: l.attribute_id.create_variant != 'no_variant').ids)
        product = products.filtered(
            lambda p: sorted(p.product_template_attribute_value_ids.ids) == variant_value_ids
        )
        if not product:
            product_tmpl = self.env['product.template'].browse(product_tmpl_id).exists()
            if any(line.attribute_id.create_variant == 'dynamic' for line in product_tmpl.attribute_line_ids):
                product = product_tmpl._create_product_variant(ptav_ids)
        return product, note, price_extra, ptav_ids

    def _process_urbanpiper_order_line(self, line_data, urbanpiper_store):
        """ Process an UrbanPiper order line and convert it into a POS order line command."""
        options_data = line_data.get('options_to_add', [])
        product_tmpl_id = int(line_data['merchant_id'].split('-')[0])  # Split is required to support records that were already synced.
        pos_config = urbanpiper_store.config_id
        currency = pos_config.currency_id
        line_qty = int(line_data['quantity'])

        product, note, price_extra, ptav_ids = self._get_urbanpiper_product_variant(options_data, product_tmpl_id)
        if not product:
            pos_config.log_urbanpiper(f'UrbanPiper: Order line skipped - no valid product found for id:{product_tmpl_id}.', 'UrbanPiper product missing', func='_process_urbanpiper_order_line')
            return False
        price_unit = float(line_data['price'] + price_extra)
        line_taxes = product.taxes_id.filtered_domain(self.env['account.tax']._check_company_domain(pos_config.company_id))
        tax_types = line_taxes.flatten_taxes_hierarchy().mapped('price_include')
        if line_data.get('taxes'):
            if tax_types and len(set(tax_types)) >= 1 and tax_types[0]:
                tax_value_sum = sum(tax.get('value', 0) for tax in line_data['taxes'])
                price_unit = float((line_data['price'] + price_extra) + (tax_value_sum / line_qty))
        elif line_taxes:
            # When 'taxes' are not provided in the payload, it indicates a tax-included price.
            # In that case, price_unit is computed using the base lines.
            base_line = line_taxes._prepare_base_line_for_taxes_computation(
                self.env['pos.order.line'],
                currency_id=currency,
                tax_ids=line_taxes,
                price_unit=price_unit,
                quantity=1,
                special_mode='total_included',
                product_id=product
            )
            line_taxes._add_tax_details_in_base_line(base_line, pos_config.company_id)
            line_taxes._round_base_lines_tax_details([base_line], pos_config.company_id)
            price_unit = base_line['tax_details']['total_included'] if tax_types and tax_types[0] else base_line['tax_details']['total_excluded']

        if fiscal := urbanpiper_store.preset_id.fiscal_position_id:
            line_taxes = fiscal.map_tax(line_taxes)
        taxes = line_taxes.compute_all(price_unit, currency, line_qty, product=product)
        total_included = taxes['total_included']

        # Handle product-level discounts
        line_discounts = line_data.get('discounts', [])
        aggregator_discount_note = '\n'.join([
            _("Aggregator Discount: %(currency)s %(value)s", currency=currency.symbol, value=discount.get('value'))
            for discount in line_discounts if not discount.get('is_merchant_discount')
        ])
        merchant_discount_value = sum(discount.get('value', 0) for discount in line_discounts if discount.get('is_merchant_discount'))
        discount_percentage = currency.round((merchant_discount_value / total_included) * 100) if merchant_discount_value and total_included else 0

        return Command.create({
            'product_id': product.id,
            'full_product_name': line_data['title'],
            'qty': line_qty,
            'attribute_value_ids': ptav_ids.ids,
            'price_extra': price_extra,
            'price_unit': price_unit,
            'price_subtotal': taxes['total_excluded'],
            'price_subtotal_incl': total_included,
            'discount': discount_percentage,
            'tax_ids': [Command.set(line_taxes.ids)] if line_taxes else None,
            'note': self._reframe_notes(f'{note}\n{aggregator_discount_note}'),
            'customer_note': line_data.get('instructions'),
            'urbanpiper_tax_liability': self._get_line_tax_liability(line_data.get('taxes')),
        })

    def _process_urbanpiper_charges(self, charges_data, lines, urbanpiper_store):
        """ Process UrbanPiper charges and append them as POS order lines. """
        pos_config = urbanpiper_store.config_id
        [other_charges, delivery_charges, packaging_charges] = pos_config.get_urbanpiper_special_products()
        for charge in charges_data:
            charge_title = charge.get('title', '').lower()
            if not charge.get('value'):
                continue
            charge_product = (
                delivery_charges if 'delivery' in charge_title
                else packaging_charges if 'packaging' in charge_title
                else other_charges
            )
            if not charge_product:
                charge_product = self.env['product.product'].search(
                    [('name', '=', 'UrbanPiper Charges')], limit=1
                ) or self.env['product.product'].create({
                    'name': 'UrbanPiper Charges',
                    'type': 'service',
                    'list_price': 0,
                    'available_in_pos': True,
                    'taxes_id': [(5,)],
                })

            charge_taxes = charge_product.taxes_id.filtered_domain(self.env['account.tax']._check_company_domain(urbanpiper_store.company_id))
            if fiscal := urbanpiper_store.preset_id.fiscal_position_id:
                charge_taxes = fiscal.map_tax(charge_taxes)
            taxes = charge_taxes.compute_all(charge.get('value'), pos_config.currency_id, 1, product=charge_product)
            lines.append(Command.create({
                'product_id': charge_product.id,
                'full_product_name': charge.get('title', charge_product.name),
                'qty': 1,
                'price_unit': charge.get('value'),
                'tax_ids': [Command.set(charge_taxes.ids)],
                'price_subtotal': taxes['total_excluded'],
                'price_subtotal_incl': taxes['total_included'],
                'note': self._reframe_notes(charge.get('title')),
                'urbanpiper_tax_liability': self._get_line_tax_liability(charge.get('taxes')),
            }))

    def _process_urbanpiper_discounts(self, discounts_data):
        """
        Process UrbanPiper merchant discounts and apply them as global discount lines.
        Computes discounts on eligible order lines with proper tax handling.
        """
        self.ensure_one()
        merchant_discount_data = [discount for discount in discounts_data if discount.get('is_merchant_discount')]
        if not merchant_discount_data:
            return

        config = self.config_id
        discount_product = (
            config.discount_product_id
            or self.env.ref('pos_discount.product_product_consumable', False)
            or self.env['product.product'].search([('default_code', '=', 'DISC')], limit=1)
        )
        if not discount_product:
            discount_product = self.env['product.product'].create({
                'name': 'Discount',
                'type': 'service',
                'list_price': 0,
                'available_in_pos': True,
                'taxes_id': [(5, 0, 0)],
                'default_code': 'DISC'
            })
        AccountTax = self.env['account.tax'].sudo()
        base_lines = []
        excluded_product_ids = config.get_urbanpiper_special_products()
        for line in self.lines:
            if line.product_id in excluded_product_ids:
                continue
            base_line = AccountTax._prepare_base_line_for_taxes_computation(
                line,
                currency_id=self.currency_id,
                tax_ids=line.tax_ids_after_fiscal_position,
                price_unit=line.price_unit,
                quantity=line.qty,
                product_id=line.product_id,
                discount=line.discount,
            )
            base_lines.append(base_line)
        AccountTax._add_tax_details_in_base_lines(base_lines, config.company_id)
        AccountTax._round_base_lines_tax_details(base_lines, config.company_id)

        def grouping_function(base_line):
            return {'product_id': discount_product}

        for discount in merchant_discount_data:
            discount_base_lines = AccountTax._prepare_global_discount_lines(
                base_lines=base_lines,
                company=config.company_id,
                amount_type='fixed',
                amount=discount.get('value'),
                computation_key=f'global_discount,{self.id}',
                grouping_function=grouping_function,
            )
            for discount_base_line in discount_base_lines:
                self.env['pos.order.line'].create({
                    'order_id': self.id,
                    'product_id': discount_product.id,
                    'price_unit': discount_base_line['price_unit'],
                    'price_subtotal': discount_base_line['tax_details']['total_excluded_currency'],
                    'price_subtotal_incl': discount_base_line['tax_details']['total_included_currency'],
                    'qty': discount_base_line['quantity'],
                    'tax_ids': discount_base_line['tax_ids'],
                    'extra_tax_data': AccountTax._export_base_line_extra_tax_data(discount_base_line),
                    'note': self._reframe_notes('\n'.join([discount.get('code', discount.get('title', ''))])),
                })

    def process_urbanpiper_order_status_update(self, data, urbanpiper_store):
        """
        # UrbanPiper Webhook Handler
        Update UrbanPiper order-status webhook data and update the corresponding order status.
        """
        self.ensure_one()
        current_status_seq = ORDER_STATUS_MAPPING[self.delivery_status.replace('_', ' ').title()][0]
        [new_status_seq, new_delivery_status] = ORDER_STATUS_MAPPING[data['new_state']]
        if current_status_seq >= new_status_seq:
            self.env['pos.config'].log_urbanpiper(f"UrbanPiper: Status of Order {data['order_id']} is already up-to-date", 'UrbanPiper Order staus is up-to-date', log_xml=False)
            return
        self.delivery_status = new_delivery_status
        if self.state == 'draft' and self.delivery_status in ('food_ready', 'dispatched', 'completed'):
            self._make_urbanpiper_order_payment()
        if self.delivery_status == 'cancelled' and self.state != 'cancel':
            self.with_context(active_ids=self.ids).action_pos_order_cancel()
            self.message_post(body=_('Order cancelled due to %s', data.get('message', _('Unknown reason'))))
        self.config_id._notify_delivery_order(self.id)

    def process_urbanpiper_rider_status(self, data, urbanpiper_store):
        """
        # UrbanPiper Webhook Handler
        Update UrbanPiper order rider information.
        """
        self.ensure_one()
        self.delivery_rider_json = json.dumps(data['delivery_info'])
        self.config_id._notify_delivery_order()

    def order_status_update(self, new_status, code=None, extra_args={}):
        """
        Update the order status from the POS UI and synchronize the updated
        status with UrbanPiper.
        """
        self.ensure_one()
        if new_status == 'Food Ready' and self.state == 'draft':
            self._make_urbanpiper_order_payment()
            if extra_args.get('preparation_time'):
                self.preparation_time = extra_args['preparation_time']

        is_success, message = True, ''
        self.prep_time = extra_args.get('orderPrepTime', 0)
        urban_piper_test = self._is_urbanpiper_test_order()
        connector = UrbanPiperConnector(self.config_id.urbanpiper_store_id)
        if not urban_piper_test:
            if (self.delivery_provider_id.technical_name != 'careem' or new_status != 'Food Ready'):
                response = connector.post_order_status(self.delivery_identifier, new_status, self.prep_time, code)
                is_success = response.get('status') == 'success'
                message = response.get('message') or next(iter(response.get('errors', {}).values()), '')
            if is_success and new_status == 'Acknowledged':
                connector.post_order_reference_update(self)
        if is_success:
            self.delivery_status = ORDER_STATUS_MAPPING[new_status][1]
            if new_status == 'Cancelled':
                self.state = 'cancel'
                cancellation_reason = self.env.context.get(
                    'cancellation_reason',
                    _('Unknown reason'),
                )
                self.message_post(
                    body=_(
                        'Order cancelled by %(cancelled_by)s due to %(cancellation_reason)s',
                        cancelled_by=self.env.context.get('cancelled_by'),
                        cancellation_reason=cancellation_reason,
                    ),
                )
        self.config_id._notify_delivery_order(is_success and self.id)
        return {'is_success': is_success, 'message': message}

    def _is_urbanpiper_test_order(self):
        """ Return True if the order is marked as an UrbanPiper test order."""
        self.ensure_one()
        if self.delivery_json:
            delivery_data = json.loads(self.delivery_json)
            return bool(delivery_data.get('order', {}).get('urban_piper_test'))

    def _make_urbanpiper_order_payment(self):
        """
        Process the payment for an UrbanPiper order using the configured provider
        payment method.

        This method should be invoked when an order is accepted or auto-accepted.
        """
        self.ensure_one()
        aggregators = self.config_id.urbanpiper_store_id.aggregator_lines
        payment_method = (
            aggregators.filtered_domain([('delivery_provider_id', '=', self.delivery_provider_id.id)]).payment_method_id
            or aggregators.payment_method_id[0]
        )
        self.env['pos.make.payment'].with_context({'active_id': self.id}).create({
            'amount': self.amount_total,
            'payment_method_id': payment_method.id,
        }).check()
        self._compute_prices()

    def write(self, vals):
        """
        For orders linked to UrbanPiper delivery (delivery_identifier set),
        this method records partner_id and amount_total changes in the chatter
        as HTML tracking messages.
        """
        if delivery_orders := self.filtered('delivery_identifier'):
            is_partner_in_vals = 'partner_id' in vals
            is_amount_total_in_vals = 'amount_total' in vals
            if is_partner_in_vals or is_amount_total_in_vals:
                partner = self.env['res.partner'].browse(vals['partner_id']) if is_partner_in_vals else None
                item_template = Markup("""
                                    <li>
                                        <span class='o-mail-Message-trackingOld me-1 px-1 text-muted fw-bold'>{old}</span>
                                        <i class='oi o-mail-Message-trackingSeparator mx-1 text-600' data-icon='east'/>
                                        <span class='o-mail-Message-trackingNew me-1 fw-bold text-info'>{new}</span>
                                        <span class='o-mail-Message-trackingField ms-1 fst-italic text-muted'>({field})</span>
                                    </li>
                            """)

                def _tracking_message_item(old_value, new_value, field_str):
                    return item_template.format(
                        old=old_value,
                        new=new_value,
                        field=field_str,
                    )
                partner_field_str = self._fields['partner_id'].string
                amount_total_field_str = self._fields['amount_total'].string
                for order in delivery_orders:
                    body_data = []
                    if is_partner_in_vals and order.partner_id != partner:
                        body_data.append(
                            _tracking_message_item(
                                old_value=order.partner_id._get_html_link() if order.partner_id else None,
                                new_value=partner._get_html_link() if partner else None,
                                field_str=partner_field_str
                            )
                        )
                    if is_amount_total_in_vals and order.amount_total and vals['amount_total'] != order.amount_total:
                        body_data.append(
                            _tracking_message_item(
                                old_value=order.amount_total,
                                new_value=vals['amount_total'],
                                field_str=amount_total_field_str
                            )
                        )
                    if body_data:
                        body = Markup('<ul>') + Markup('').join(body_data) + Markup('</ul>')
                        order.message_post(body=body)

        return super().write(vals)
