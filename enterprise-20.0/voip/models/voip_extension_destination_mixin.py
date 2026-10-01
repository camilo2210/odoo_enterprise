from odoo import api, fields, models


class VoipExtensionDestinationMixin(models.AbstractModel):
    _name = "voip.extension.destination.mixin"
    _description = "PBX Extension Destination"

    routing_extension_id = fields.Many2one(
        "voip.extension",
        string="Extension Record",
        compute="_compute_routing_extension",
        compute_sudo=True,
    )
    routing_extension_number = fields.Char(
        string="Extension",
        compute="_compute_routing_extension",
        compute_sudo=True,
        inverse="_inverse_routing_extension_number",
        search="_search_routing_extension_number",
    )
    has_routing_extension = fields.Boolean(
        compute="_compute_routing_extension",
        compute_sudo=True,
        search="_search_has_routing_extension",
    )

    def _compute_routing_extension(self):
        extensions_by_destination = {
            extension.destination_ref.id: extension
            for extension in self.env["voip.extension"].search([
                ("destination_ref", "in", [
                    f"{record._name},{record.id}"
                    for record in self
                ]),
            ])
        }
        for record in self:
            extension = extensions_by_destination.get(record.id)
            record.routing_extension_id = extension
            record.routing_extension_number = extension.number if extension else False
            record.has_routing_extension = bool(extension)

    def _inverse_routing_extension_number(self):
        extensions_by_destination = {
            extension.destination_ref.id: extension
            for extension in self.env["voip.extension"].search([
                ("destination_ref", "in", [
                    f"{record._name},{record.id}"
                    for record in self
                ]),
            ])
        }
        for record in self:
            extension_number = record.routing_extension_number and record.routing_extension_number.strip()
            extension = extensions_by_destination.get(record.id)
            if not extension_number:
                if extension:
                    extension.unlink()
            elif extension:
                extension.number = extension_number
            else:
                self.env["voip.extension"].create({
                    "number": extension_number,
                    "destination_ref": f"{record._name},{record.id}",
                })

    def _search_routing_extension_number(self, operator, value):
        matching_extensions = self.env["voip.extension"].search([
            ("destination_ref", "=like", f"{self._name},%"),
            ("number", operator, value),
        ])
        return [("id", "in", [
            extension.destination_ref.id
            for extension in matching_extensions
            if extension.destination_ref
        ])]

    def _search_has_routing_extension(self, operator, value):
        # The ORM normalizes "=" / "!=" on a boolean field into "in" / "not in"
        # with a set of values before calling a field's search=; handle both
        # forms so this keeps working regardless of that normalization.
        if operator == "=":
            wants_extension = bool(value)
        elif operator == "!=":
            wants_extension = not value
        elif operator == "in":
            wants_extension = True in value
        elif operator == "not in":
            wants_extension = True not in value
        else:
            raise ValueError(f"Unsupported operator {operator!r} for has_routing_extension search.")
        extensions = self.env["voip.extension"].search([
            ("destination_ref", "=like", f"{self._name},%"),
        ])
        destination_ids = [
            extension.destination_ref.id
            for extension in extensions
            if extension.destination_ref
        ]
        return [("id", "in" if wants_extension else "not in", destination_ids)]

    @api.ondelete(at_uninstall=False)
    def _unlink_routing_extension(self):
        if self.env.context.get("voip_skip_pbx_sync"):
            return
        self.env["voip.extension"].search([
            ("destination_ref", "in", [
                f"{record._name},{record.id}"
                for record in self
            ]),
        ]).unlink()
