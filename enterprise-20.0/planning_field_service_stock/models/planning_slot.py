from collections import defaultdict
from odoo import api, fields, models
from odoo.fields import Domain


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    lot_ids = fields.Many2many(
        'stock.lot',
        string='Lot/Serial Number',
        compute='_compute_lot_ids',
        inverse='_inverse_lot_ids',
        store=True,
        readonly=False,
        init_storage=lambda model: None,
    )
    is_planning_admin = fields.Boolean(compute='_compute_is_planning_admin', export_string_translation=False)
    product_document_count = fields.Integer(compute='_compute_product_document_count', export_string_translation=False)

    @api.depends_context('uid')
    def _compute_is_planning_admin(self):
        self.is_planning_admin = self.env.user.has_group('planning.group_planning_manager')

    @api.depends('partner_id')
    def _compute_lot_ids(self):
        if not self.env.user.has_group('planning.group_field_service_allow_equipment'):
            return

        shifts_to_compute = self.filtered(lambda s: s.partner_id)
        if not shifts_to_compute:
            return

        lots = self.env['stock.lot'].search([('partner_ids', 'child_of', shifts_to_compute.partner_id.ids)])

        lots_by_commercial_partner = defaultdict(lambda: self.env['stock.lot'])
        for lot in lots:
            for partner in lot.partner_ids:
                lots_by_commercial_partner[partner.commercial_partner_id] |= lot

        for slot in shifts_to_compute:
            expected_lots = lots_by_commercial_partner.get(
                slot.partner_id.commercial_partner_id,
                self.env['stock.lot']
            )

            if slot.lot_ids and (slot.lot_ids._origin <= expected_lots):
                continue
            slot.lot_ids = expected_lots

    @api.depends('lot_ids')
    def _compute_product_document_count(self):
        if not self.lot_ids:
            self.product_document_count = 0
            return
        document_groups = self.env['product.document']._read_group(
            self._get_product_document_domain(),
            ['res_model', 'res_id'],
            ['__count'],
        )
        documents_count = {(res_model, res_id): count for res_model, res_id, count in document_groups}
        for slot in self:
            products = slot.lot_ids.product_id
            slot.product_document_count = (
                sum(documents_count.get(('product.product', product.id), 0) for product in products)
                + sum(documents_count.get(('product.template', template.id), 0) for template in products.product_tmpl_id)
            )

    def action_open_documents(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('planning_field_service_stock.planning_slot_action_documents')
        action['domain'] = self._get_product_document_domain()
        return action

    def _get_product_document_domain(self):
        products = self.lot_ids.product_id
        return Domain.OR([
            [('res_model', '=', 'product.product'), ('res_id', 'in', products.ids)],
            [('res_model', '=', 'product.template'), ('res_id', 'in', products.product_tmpl_id.ids)],
        ])

    def _inverse_lot_ids(self):
        for slot in self:
            slot.lot_ids -= slot.lot_ids.filtered(
                lambda lot: slot.partner_id.commercial_partner_id
                not in lot.partner_ids.mapped('commercial_partner_id')
            )
