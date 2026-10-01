# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain

from ..utils.urbanpiper_connector import UrbanPiperConnector


class UrbanPiperStoreAggregator(models.Model):
    _name = 'urbanpiper.store.aggregator'
    _inherit = 'pos.load.mixin'
    _description = 'UrbanPiper Aggregators and their related information for Online Food Delivery Stores'

    store_id = fields.Many2one(
        'pos.urbanpiper.store',
        string='UrbanPiper Store',
        index='btree',
        readonly=True
    )
    company_id = fields.Many2one(related="store_id.company_id")
    delivery_provider_id = fields.Many2one(
        'pos.delivery.provider',
        string='Delivery Aggregator',
        required=True,
        help="Delivery providers used for online delivery through UrbanPiper.",
    )
    pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Pricelist',
        help=(
            "Pricelist used by the UrbanPiper delivery aggregator to update prices during menu syncing.\n"
            "If not set, product prices will be based on the store preset pricelist"
        )
    )
    is_online = fields.Boolean(string='Is Online?', help="Indicates whether this aggregator is currently active on UrbanPiper.")
    payment_method_id = fields.Many2one(
        'pos.payment.method',
        string='UrbanPiper Payment Method',
        compute='_compute_payment_method',
        store=True,
        readonly=True,
        help="Payment method used for online order payments."
    )
    use_create_customer = fields.Boolean(
        string='Create Customer',
        default=True,
        help="Indicates whether a customer should be created for this aggregator if it is not created before."
    )
    default_customer_id = fields.Many2one(
        'res.partner',
        string='Default Customer',
        check_company=True,
        readonly=True,
        help="Customer used for orders when 'Use Default Customer' is selected."
    )
    has_active_store_session = fields.Boolean(compute='_compute_has_active_store_session')

    @api.constrains('is_online', 'store_id')
    def _check_online_store_session(self):
        if any(not aggregator.store_id.config_id.has_active_session for aggregator in self.filtered('is_online')):
            raise ValidationError(
                _("Cannot update availability: the associated Point of Sale session is currently closed.")
            )

    @api.depends('store_id')
    def _compute_has_active_store_session(self):
        for aggregator in self:
            store = aggregator.store_id
            aggregator.has_active_store_session = (store.is_webhook_register and store.config_id.has_active_session)

    @api.depends('store_id', 'delivery_provider_id')
    def _compute_display_name(self):
        for aggregator in self:
            aggregator.display_name = f'{aggregator.delivery_provider_id.name} - {aggregator.store_id.name}'

    @api.depends('delivery_provider_id')
    def _compute_payment_method(self):
        """
        Ensure the aggregator has a payment method linked to its delivery provider.
        If the required journal or payment method does not exist, it is created.
        """
        Journal = self.env['account.journal'].sudo()
        PaymentMethod = self.env['pos.payment.method']

        for aggregator in self:
            chart_template = aggregator.with_context(allowed_company_ids=aggregator.company_id.root_id.ids).env['account.chart.template']
            outstanding_account = chart_template.ref('account_journal_payment_debit_account_id', raise_if_not_found=False) or aggregator.company_id.transfer_account_id

            provider = aggregator.delivery_provider_id
            store = aggregator.store_id
            company = store.company_id
            journal_code = f"{provider.journal_code}{store.id}"

            journal = Journal.search([
                *self.env['account.journal']._check_company_domain(company),
                ('code', '=', journal_code),
            ], limit=1) or Journal.create({
                'name': f"{provider.name} - {store.name}",
                'code': journal_code,
                'type': 'bank',
                'company_id': company.id,
                'show_on_dashboard': False,
            })

            payment_method = PaymentMethod.search([
                ('journal_id', '=', journal.id),
                ('delivery_provider_id', '=', provider.id),
            ], limit=1) or PaymentMethod.create({
                'name': f"{provider.name} - {store.name}",
                'journal_id': journal.id,
                'type': 'bank',
                'company_id': company.id,
                'outstanding_account_id': outstanding_account.id,
                'delivery_provider_id': provider.id,
            })

            aggregator.payment_method_id = payment_method

    @api.model
    def _load_pos_data_fields(self, config):
        return ['store_id', 'delivery_provider_id', 'payment_method_id', 'is_online']

    @api.model
    def _load_pos_data_domain(self, data):
        if not data['pos.config'].module_pos_urban_piper:
            return Domain.FALSE
        return Domain('store_id', '=', data['pos.config'].urbanpiper_store_id.id)

    def write(self, vals):
        res = super().write(vals)
        if 'is_online' in vals:
            self._update_store_status(vals['is_online'])
        return res

    def _update_store_status(self, new_status):
        """Activate or deactivate the store for the delivery aggregator."""
        for store, aggregators in self.grouped('store_id').items():
            connector = UrbanPiperConnector(store)
            connector.post_locations_status(new_status, aggregators.delivery_provider_id.ids)
            # Kepp in sync the POS UI
            store.config_id.notify_synchronisation(
                store.config_id.current_session_id.id,
                device_identifier=self.env.context.get('device_identifier', False),
                records={'urbanpiper.store.aggregator': aggregators.ids}
            )

    def _get_order_customer(self, customer_data):
        """Return the customer for an UrbanPiper order based on the customer creation configuration."""
        self.ensure_one()

        if not self.use_create_customer:
            if self.default_customer_id:
                return self.default_customer_id
            customer = self.search([
                ('company_id', '=', self.company_id.id),
                ('delivery_provider_id', '=', self.delivery_provider_id.id),
                ('default_customer_id', '!=', False),
            ], limit=1).default_customer_id
            if not customer:
                customer = self.env['res.partner'].create({
                    'name': self.delivery_provider_id.name,
                    'company_id': self.company_id.id,
                    'country_id': self.company_id.country_id.id,
                    'active': False,
                })
            self.default_customer_id = customer
            return customer

        customer_address = customer_data['address']
        customer_vals = {
            'name': customer_data['name'],
            'phone': customer_data['phone'],
            'email': customer_data['email'],
            'street': customer_address.get('line_1'),
            'street2': customer_address.get('line_2'),
            'city': customer_address.get('city'),
            'zip': customer_address.get('pin'),
        }
        if existing_customer := self.env['res.partner'].search([
            ('name', '=', customer_data['name']),
            ('phone', '=', customer_data['phone'])
        ], limit=1):
            return existing_customer
        return self.env['res.partner'].create(customer_vals)
