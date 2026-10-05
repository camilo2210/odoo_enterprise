# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class BaseDueDiligenceMixin(models.AbstractModel):
    """
    Mixin abstracto reutilizable: campos y lógica de Due Diligence.

    Contiene:
    - Campo booleano `due_diligence`
    - Campo fecha `due_diligence_date`
    - Constrains: si due_diligence es True, la fecha es obligatoria

    Uso:
        class ResPartner(models.Model):
            _name = 'res.partner'
            _inherit = ['res.partner', 'base.due.diligence.mixin']
    """

    _name = "base.due.diligence.mixin"
    _description = "Mixin de Due Diligence"

    # -------------------------------------------------------------------------
    # Campos de due diligence
    # -------------------------------------------------------------------------

    due_diligence = fields.Boolean(
        string="Due Diligence",
        default=False,
        help="Indica si se realizó proceso de Due Diligence para este registro.",
    )
    due_diligence_date = fields.Date(
        string="Fecha Due Diligence",
        help="Fecha en la que se realizó el proceso de Due Diligence. "
             "Obligatorio si Due Diligence está activo.",
    )

    # -------------------------------------------------------------------------
    # Validaciones
    # -------------------------------------------------------------------------

    @api.constrains("due_diligence", "due_diligence_date")
    def _check_due_diligence_date(self):
        """
        Valida que si due_diligence está activo, due_diligence_date
        sea obligatorio. Aplica a todos los modelos que hereden este mixin.
        """
        for record in self:
            if record.due_diligence and not record.due_diligence_date:
                raise ValidationError(
                    _(
                        "El campo 'Fecha Due Diligence' es obligatorio "
                        "cuando 'Due Diligence' está activo.\n"
                        "Registro: %s"
                    )
                    % (record.display_name or record.id)
                )

    # -------------------------------------------------------------------------
    # Métodos utilitarios (opcionales, disponibles para todos los modelos)
    # -------------------------------------------------------------------------

    def action_reset_due_diligence(self):
        """
        Método utilitario: reinicia el proceso de due diligence.
        Puede llamarse desde botones en cualquier vista que herede este mixin.
        """
        self.ensure_one()
        self.write({
            "due_diligence": False,
            "due_diligence_date": False,
        })
