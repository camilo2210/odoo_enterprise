# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models


def post_init(env):
    field_service_product = env.ref("planning_field_service.field_service_product", raise_if_not_found=False)
    if field_service_product:
        field_service_product.write({
            "worksheet_template_id": env.ref("planning_field_service_worksheet.fsm_worksheet_template").id,
        })
