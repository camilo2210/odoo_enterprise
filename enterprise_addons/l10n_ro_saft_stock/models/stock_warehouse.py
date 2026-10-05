from odoo import _, models
from odoo.exceptions import ValidationError


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    def _create_or_update_sequences_and_picking_types(self):
        # EXTENDS stock
        # to set correct return picking types for Romanian companies
        warehouse_data = super()._create_or_update_sequences_and_picking_types()
        company = self.company_id or self.env.company

        if company.country_code == 'RO':
            PickingType = self.env['stock.picking.type']
            in_picking_type_id = self.in_type_id or PickingType.browse(warehouse_data.get('in_type_id'))
            if not in_picking_type_id:
                raise ValidationError(_("Missing configuration: No incoming picking type found for warehouse %s."), self.name)
            return_picking_type_id = in_picking_type_id.return_picking_type_id
            if not return_picking_type_id or return_picking_type_id.sequence_code != 'INR':
                inr_picking_type = self.env['stock.picking.type'].search([
                    ('sequence_code', '=', 'INR'),
                    ('warehouse_id', '=', self.id),
                    '|', ('company_id', '=', self.company_id.id), ('company_id', '=', False)
                ], limit=1)
                if inr_picking_type:
                    return_picking_type_id = inr_picking_type
                else:
                    return_picking_type_id = self.env['stock.picking.type'].create({
                        'name': self.env._('Return of purchase'),
                        'code': 'outgoing',
                        'sequence_code': 'INR',
                        'company_id': company.id,
                        'warehouse_id': self.id,
                        'l10n_ro_stock_movement_type': '50',
                    })
                in_picking_type_id.return_picking_type_id = return_picking_type_id
            if return_picking_type_id.return_picking_type_id != in_picking_type_id:
                return_picking_type_id.return_picking_type_id = in_picking_type_id

            out_picking_type_id = self.out_type_id or PickingType.browse(warehouse_data.get('out_type_id'))
            if not out_picking_type_id:
                raise ValidationError(_("Missing configuration: No outgoing picking type found for warehouse %s."), self.name)
            return_picking_type_id = out_picking_type_id.return_picking_type_id
            if not return_picking_type_id or return_picking_type_id.sequence_code != 'OUTR':
                outr_picking_type = self.env['stock.picking.type'].search([
                    ('sequence_code', '=', 'OUTR'),
                    ('warehouse_id', '=', self.id),
                    '|', ('company_id', '=', self.company_id.id), ('company_id', '=', False)
                ], limit=1)
                if outr_picking_type:
                    return_picking_type_id = outr_picking_type
                else:
                    return_picking_type_id = self.env['stock.picking.type'].create({
                        'name': self.env._('Return of sales'),
                        'code': 'incoming',
                        'sequence_code': 'OUTR',
                        'company_id': company.id,
                        'warehouse_id': self.id,
                        'l10n_ro_stock_movement_type': '40',
                    })
                out_picking_type_id.return_picking_type_id = return_picking_type_id
            if return_picking_type_id.return_picking_type_id != out_picking_type_id:
                return_picking_type_id.return_picking_type_id = out_picking_type_id

        return warehouse_data
