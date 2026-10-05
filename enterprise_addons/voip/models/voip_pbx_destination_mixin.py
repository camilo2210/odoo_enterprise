from odoo import api, fields, models


class VoipPbxDestinationMixin(models.AbstractModel):
    _name = "voip.pbx.destination.mixin"
    _description = "PBX Destination"

    is_call_flow_node_configuration = fields.Boolean(
        compute="_compute_is_call_flow_node_configuration",
    )

    @api.depends_context("voip_call_flow_node_configuration")
    def _compute_is_call_flow_node_configuration(self):
        is_node_configuration = bool(self.env.context.get("voip_call_flow_node_configuration"))
        for record in self:
            record.is_call_flow_node_configuration = is_node_configuration

    def _get_pbx_reference_owners(self):
        """Return PBX records whose stored routes reference this destination."""
        references = [f"{record._name},{record.id}" for record in self]

        user_settings = self.env["res.users.settings"].sudo().search([
            "|",
            ("voip_no_answer_destination_ref", "in", references),
            ("voip_busy_destination_ref", "in", references),
        ])

        call_groups = self.env["voip.call.group"].sudo().search([
            ("no_answer_destination_ref", "in", references),
        ])

        queues = self.env["voip.queue"].sudo().search([
            "|",
            ("no_answer_destination_ref", "in", references),
            ("busy_destination_ref", "in", references),
        ])

        ivrs = self.env["voip.ivr"].sudo().search([
            "|", "|",
            ("invalid_destination_ref", "in", references),
            ("timeout_destination_ref", "in", references),
            ("abort_destination_ref", "in", references),
        ])
        ivrs |= self.env["voip.ivr.option"].sudo().search([
            ("destination_ref", "in", references),
        ]).ivr_id

        time_conditions = self.env["voip.time.condition"].sudo().search([
            "|",
            ("open_destination_ref", "in", references),
            ("closed_destination_ref", "in", references),
        ])

        routed_dids = self.env["voip.did.number"].sudo().search([
            ("destination_ref", "in", references),
        ])
        routed_dids |= self.env["voip.did.number"].sudo().search([
            ("destination_ref", "in", [
                f"voip.call.flow,{call_flow.id}"
                for call_flow in time_conditions.callflow_id
            ]),
        ])
        return {
            "res.users.settings": user_settings,
            "voip.call.group": call_groups,
            "voip.queue": queues,
            "voip.ivr": ivrs,
            "voip.time.condition": time_conditions,
            "voip.did.number": routed_dids,
        }

    def _sync_pbx_references(self):
        """Resync routes that embed this destination in their PBX payload."""
        references = self._get_pbx_reference_owners()
        references["res.users.settings"]._voip_sync_pbx()
        references["voip.call.group"]._sync_pbx_routing()
        references["voip.queue"]._sync_pbx_routing()
        references["voip.ivr"]._sync_pbx()
        references["voip.time.condition"]._sync_pbx()
        references["voip.did.number"]._sync_pbx_incall()

    @api.ondelete(at_uninstall=False)
    def _unlink_did_routes(self):
        routed_numbers = self.env["voip.did.number"].sudo().search([
            ("destination_ref", "in", [
                f"{record._name},{record.id}"
                for record in self
            ]),
        ])
        if routed_numbers:
            routed_numbers.write({"destination_ref": False})
