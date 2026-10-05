# -*- coding: utf-8 -*-
{
    "name": "Base Custom Fields",
    "summary": "Módulo base reutilizable para extender modelos con campos personalizados",
    "description": """
        Proporciona mixins abstractos y extensiones de modelos estándar de Odoo,
        facilitando la adición de campos de compliance, due diligence y consultas
        a centrales de riesgo sin modificar el núcleo del sistema.
    """,
    "version": "19.0.1.0.0",
    "category": "Technical",
    "author": "Tu Empresa",
    "website": "https://tuempresa.com",
    "license": "LGPL-3",
    "depends": [
        "base",
        "contacts",
        "sale_management",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_partner_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}


