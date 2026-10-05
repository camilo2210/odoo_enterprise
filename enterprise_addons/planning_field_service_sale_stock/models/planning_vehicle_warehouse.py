from odoo import models, fields, api
from odoo.exceptions import ValidationError


class PlanningVehicleWarehouse(models.Model):
    _name = 'planning.vehicle.warehouse'
    _description = 'Vehicle Warehouse Mapping'
    _rec_name = 'warehouse_id'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='warehouse_id.company_id',
    )

    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Warehouse (Vehicle)',
        required=True,
        check_company=True,
    )

    user_ids = fields.Many2many(
        'res.users',
        'planning_vehicle_warehouse_user_rel',
        'vehicle_id', 'user_id',
        string='Assigned to',
    )

    _check_warehouse_uniq = models.Constraint('UNIQUE(warehouse_id)', 'This warehouse is already configured as a vehicle.')

    @api.constrains('user_ids', 'warehouse_id')
    def _check_unique_user_per_company(self):
        vehicles_with_users = self.filtered('user_ids')
        if not vehicles_with_users:
            return

        count_per_company_per_user = self.env['planning.vehicle.warehouse']._read_group(
            domain=[
                ('company_id', 'in', vehicles_with_users.company_id.ids),
                ('user_ids', 'in', vehicles_with_users.user_ids.ids),
            ],
            groupby=['user_ids', 'company_id'],
            aggregates=['__count'],
            having=[('__count', '>', 1)]
        )
        if count_per_company_per_user:
            problematic_users = [user.name for user, company, count in count_per_company_per_user]
            unique_problematic_users = list(set(problematic_users))
            raise ValidationError(
                self.env._(
                    "A user can only be assigned to one vehicle per company.\n\n"
                    "The following users are assigned to multiple vehicles: %s"
                ) % ", ".join(unique_problematic_users)
            )

    @api.model_create_multi
    def create(self, vals_list):
        vehicles = super().create(vals_list)
        for vehicle in vehicles:
            if vehicle.warehouse_id and vehicle.user_ids:
                vehicle.user_ids.with_company(vehicle.company_id).write({
                    'property_warehouse_id': vehicle.warehouse_id.id
                })
        return vehicles

    def write(self, vals):
        old_assignments = {rec.id: rec.user_ids for rec in self}
        res = super().write(vals)
        if 'warehouse_id' in vals or 'user_ids' in vals:
            for vehicle in self:
                if 'user_ids' in vals:
                    removed_users = old_assignments[vehicle.id] - vehicle.user_ids
                    if removed_users:
                        removed_users.with_company(vehicle.company_id).write({'property_warehouse_id': False})
                if vehicle.warehouse_id:
                    vehicle.user_ids.with_company(vehicle.company_id).write({'property_warehouse_id': vehicle.warehouse_id.id})
                else:
                    vehicle.user_ids.with_company(vehicle.company_id).write({'property_warehouse_id': False})
        return res

    @api.ondelete(at_uninstall=False)
    def unlink_vehicle(self):
        for vehicle in self:
            if vehicle.user_ids:
                vehicle.user_ids.with_company(vehicle.company_id).write({'property_warehouse_id': False})
