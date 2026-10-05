from odoo import Command, api, fields, models


class EsgCarbonEmissionReport(models.Model):
    _inherit = "esg.carbon.emission.report"

    @property
    def READ_OTHER_EMISSION_FIELDS(self):
        return super().READ_OTHER_EMISSION_FIELDS | {
            "has_fleet_factor",
        }

    quantity = fields.Integer(compute="_compute_quantity", store=True, readonly=False)
    has_fleet_factor = fields.Boolean(export_string_translation=False, compute="_compute_has_fleet_factor")
    conflicting_emission_ids = fields.Many2many("esg.other.emission", compute="_compute_conflicting_emission_ids", export_string_translation=False)

    @api.depends("has_fleet_factor", "date", "date_end", "company_id")
    def _compute_quantity(self):
        emissions_to_compute = self.filtered(
            lambda e: e.id > 0 and e.has_fleet_factor and e.date and e.date_end
        )
        if not emissions_to_compute:
            return

        communting_quantity_mapping = self.env["esg.other.emission"]._get_commuting_quantity(emissions_to_compute)
        for emission in emissions_to_compute:
            emission.quantity = communting_quantity_mapping.get(emission.id, 0)

    @api.depends("esg_emission_factor_id")
    def _compute_has_fleet_factor(self):
        fleet_factor = self.env.ref("esg_hr_fleet.employee_commuting_factor")
        for emission in self:
            emission.has_fleet_factor = emission.esg_emission_factor_id == fleet_factor

    @api.depends("has_fleet_factor", "date", "date_end", "company_id")
    def _compute_conflicting_emission_ids(self):
        emissions_to_process = self.filtered(
            lambda e: e.id > 0 and e.has_fleet_factor and e.date and e.date_end
        )
        (self - emissions_to_process).conflicting_emission_ids = [Command.clear()]
        if not emissions_to_process:
            return

        conflicting_emissions_mapping = self.env["esg.other.emission"]._get_conflicting_emission_ids(emissions_to_process)
        for emission in emissions_to_process:
            emission.conflicting_emission_ids = [Command.set(conflicting_emissions_mapping.get(emission.id, []))]

    def write(self, vals):
        res = super().write(vals)
        if any(field in vals for field in ("esg_emission_factor_id", "date", "date_end", "company_id")):
            self._invalidate_cache(fnames=["conflicting_emission_ids"])
        return res
