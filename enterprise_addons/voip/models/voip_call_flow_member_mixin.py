from odoo import api, models
from odoo.exceptions import ValidationError


class VoipCallFlowMemberMixin(models.AbstractModel):
    _name = "voip.call.flow.member.mixin"
    _description = "Call Flow Member"

    _call_flow_destination_fields = frozenset()

    @api.model_create_multi
    def create(self, vals_list):
        if (
            any(vals.get("callflow_id") for vals in vals_list)
            and not self.env.context.get("voip_call_flow_sync")
        ):
            raise ValidationError(self.env._(
                "Call Flow membership can only be modified from the Call Flow."
            ))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get("voip_call_flow_sync"):
            if "callflow_id" in vals:
                raise ValidationError(self.env._(
                    "Call Flow membership can only be modified from the Call Flow."
                ))
            if self._call_flow_destination_fields & vals.keys() and self.filtered("callflow_id"):
                raise ValidationError(self.env._(
                    "The PBX destinations of records used in a Call Flow "
                    "can only be modified from that Call Flow.",
                ))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_if_call_flow_owned(self):
        if not self.env.context.get("voip_call_flow_sync") and self.filtered("callflow_id"):
            raise ValidationError(self.env._(
                "Remove this record from its Call Flow before deleting it.",
            ))
