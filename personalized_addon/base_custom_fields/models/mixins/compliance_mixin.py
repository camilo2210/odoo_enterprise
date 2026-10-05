# -*- coding: utf-8 -*-
from odoo import fields, models


class BaseComplianceMixin(models.AbstractModel):
    """
    Mixin abstracto reutilizable: campos booleanos de consulta a centrales
    de riesgo y registros públicos.

    Uso: heredar este mixin en cualquier modelo que requiera estos campos.
    Ejemplo:
        class SaleOrder(models.Model):
            _name = 'sale.order'
            _inherit = ['sale.order', 'base.compliance.mixin']
    """

    _name = "base.compliance.mixin"
    _description = "Mixin de Campos de Compliance y Consultas"

    # -------------------------------------------------------------------------
    # Campos de autorización y consulta
    # -------------------------------------------------------------------------

    autoriza_consulta_centrales = fields.Boolean(
        string="Autoriza Consulta a Centrales",
        default=False,
        help="El contacto autoriza la consulta de su información en centrales de riesgo.",
    )
    autoriza_reporte_centrales = fields.Boolean(
        string="Autoriza Reporte a Centrales",
        default=False,
        help="El contacto autoriza el reporte de su información a centrales de riesgo.",
    )
    consulta_bienes_registro = fields.Boolean(
        string="Consulta Bienes en Registro",
        default=False,
        help="Se realizó consulta de bienes inmuebles en registro público.",
    )
    consulta_vehiculos_transito = fields.Boolean(
        string="Consulta Vehículos en Tránsito",
        default=False,
        help="Se realizó consulta de vehículos en el registro de tránsito.",
    )
