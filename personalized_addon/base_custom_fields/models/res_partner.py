# -*- coding: utf-8 -*-
from odoo import models


class ResPartner(models.Model):
    """
    Extensión de res.partner con los mixins de compliance y due diligence.

    Este archivo es intencionalmente minimalista: toda la lógica y campos
    viven en los mixins. Aquí solo declaramos la herencia múltiple.

    Para agregar más campos exclusivos de res.partner que NO sean reutilizables
    en otros modelos, decláralos directamente aquí.
    """

    _name = "res.partner"
    _inherit = [
        "res.partner",
        "base.compliance.mixin",
        "base.due.diligence.mixin",
    ]

    # Campos específicos de res.partner (no reutilizables) van aquí.
    # Ejemplo futuro:
    # partner_risk_level = fields.Selection([...], string="Nivel de Riesgo")


