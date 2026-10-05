from collections import defaultdict
from datetime import date

from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError


class EsgOtherEmission(models.Model):
    _inherit = "esg.other.emission"

    has_fleet_factor = fields.Boolean(compute="_compute_has_fleet_factor", search="_search_has_fleet_factor", export_string_translation=False)
    conflicting_emission_ids = fields.Many2many("esg.other.emission", compute="_compute_conflicting_emission_ids", export_string_translation=False)
    quantity = fields.Integer(compute="_compute_quantity", readonly=False, store=True)

    @api.depends("esg_emission_factor_id")
    def _compute_has_fleet_factor(self):
        fleet_factor = self.env.ref("esg_hr_fleet.employee_commuting_factor")
        for emission in self:
            emission.has_fleet_factor = emission.esg_emission_factor_id == fleet_factor

    def _search_has_fleet_factor(self, operator, value):
        if operator not in ("=", "!=") or value not in (True, False):
            return NotImplemented
        has_factor = value if operator == "=" else not value
        fleet_factor = self.env.ref("esg_hr_fleet.employee_commuting_factor")
        return [("esg_emission_factor_id", "=" if has_factor else "!=", fleet_factor.id)]

    @api.depends("has_fleet_factor", "date", "date_end", "company_id")
    def _compute_conflicting_emission_ids(self):
        emissions_to_process = self.filtered(
            lambda e: e.has_fleet_factor and e.date and e.date_end
        )
        (self - emissions_to_process).conflicting_emission_ids = [Command.clear()]
        if not emissions_to_process:
            return

        conflicting_emissions_mapping = self._get_conflicting_emission_ids(emissions_to_process)
        for emission in emissions_to_process:
            emission.conflicting_emission_ids = [Command.set(conflicting_emissions_mapping.get(emission.id, []))]

    @api.model
    def _get_conflicting_emission_ids(self, emissions_to_process):
        mapping = {}
        min_date = min(emissions_to_process.mapped('date'))
        max_date = max(emissions_to_process.mapped('date_end'))
        company_ids = emissions_to_process.mapped('company_id')
        potential_conflict_emissions = self.env["esg.other.emission"].search([
            ("has_fleet_factor", "=", True),
            ("date", "<=", max_date),
            ("date_end", ">=", min_date),
            ("company_id", "in", company_ids.ids),
        ])
        conflict_emission_by_company = defaultdict(list)
        for conflit_emission in potential_conflict_emissions:
            conflict_emission_by_company[conflit_emission.company_id.id].append(conflit_emission)

        for emission in emissions_to_process:
            conflicting_ids = []
            conflict_emissions = conflict_emission_by_company.get(emission.company_id.id, [])
            for conflict_emission in conflict_emissions:
                if conflict_emission.id == emission._origin.id:
                    continue
                if conflict_emission.date <= emission.date_end and conflict_emission.date_end >= emission.date:
                    conflicting_ids.append(conflict_emission.id)
            mapping[emission.id] = conflicting_ids

        return mapping

    @api.depends("date", "date_end", "company_id", "has_fleet_factor")
    def _compute_quantity(self):
        emissions_to_compute = self.filtered(
            lambda e: e.has_fleet_factor and e.date and e.date_end
        )
        if not emissions_to_compute:
            return

        communting_quantity_mapping = self._get_commuting_quantity(emissions_to_compute)
        for emission in emissions_to_compute:
            emission.quantity = communting_quantity_mapping.get(emission.id, 0)

    @api.model
    def _get_commuting_quantity(self, emissions_to_compute):
        mapping = {}
        min_date = min(emissions_to_compute.mapped('date'))
        max_date = max(emissions_to_compute.mapped('date_end'))
        company_ids = emissions_to_compute.mapped('company_id')
        all_logs = self.env["fleet.vehicle.assignation.log"].search([
            ("company_id", "in", company_ids.ids),
            ("date_start", "<=", max_date),
            "|",
                ("date_end", ">=", min_date),
                ("date_end", "=", False),
        ])
        logs_by_company = defaultdict(list)
        for log in all_logs:
            logs_by_company[log.company_id.id].append(log)

        for emission in emissions_to_compute:
            total_co2 = 0.0
            company_logs = logs_by_company.get(emission.company_id.id, [])
            for log in company_logs:
                if log.date_start > emission.date_end:
                    continue
                if log.date_end and log.date_end < emission.date:
                    continue

                employee = log.driver_employee_id
                vehicle = log.vehicle_id
                if not (employee or vehicle):
                    continue

                overlap_start = max(log.date_start, emission.date)
                log_end_date = log.date_end or emission.date_end
                overlap_end = min(log_end_date, emission.date_end)

                days = (overlap_end - overlap_start).days + 1
                daily_km = (employee.distance_home_work or 0) * 2
                work_ratio = vehicle.company_id.weekly_days_at_office / 7.0

                total_co2 += days * daily_km * work_ratio * vehicle.co2 / 1_000

            mapping[emission.id] = int(total_co2)

        return mapping

    @api.model_create_multi
    def create(self, vals_list):
        fleet_factor_id = self.env.ref("esg_hr_fleet.employee_commuting_factor").id
        for vals in vals_list:
            if vals.get("esg_emission_factor_id") == fleet_factor_id:
                if not (vals.get("date") and vals.get("date_end") and vals.get("company_id")):
                    raise ValidationError(self.env._("To create a Fleet Emission, you need to specify both start and end dates, and the company of the emission."))
                start_date = date.fromisoformat(vals["date"])
                end_date = date.fromisoformat(vals["date_end"])
                if not vals.get("note"):
                    vals["note"] = self.env._(
                        "Employee commuting from %(start_date)s to %(end_date)s",
                        start_date=fields.Date.to_string(start_date),
                        end_date=fields.Date.to_string(end_date),
                    )
        return super().create(vals_list)

    def action_show_conflicting_emissions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "esg.carbon.emission.report",
            "name": self.env._("Conflicting Emissions"),
            "views": [[False, "list"], [False, "form"]],
            "domain": [("id", "in", self.conflicting_emission_ids.ids)],
        }
