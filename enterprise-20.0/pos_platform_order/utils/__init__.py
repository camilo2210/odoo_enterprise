# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.api import Environment
from odoo.models import BaseModel


def _get_external_id(record: BaseModel):
    """
    Generate a unique external ID for the given record.
    Example: product.product(1) becomes 'product_product_1'
    """
    return f"{record._name.replace('.', '_')}_{record.id}"


def _parse_external_ids(env: Environment, external_ids: list[str] | str) -> list[int]:
    """
    Parse the external ID to get the model name and record ID.
    Example: 'product_product_1' becomes product.product(1)
    """
    if isinstance(external_ids, str):
        external_ids = [external_ids]

    expected_model_name: str | None = None
    res_ids: list[int] = []

    for external_id in external_ids:
        model_prefix, res_id = external_id.rsplit('_', 1)
        model_name = model_prefix.replace('_', '.')

        if expected_model_name is None:
            if model_name not in env:
                raise ValueError(f"Model {model_name} does not exist in the environment")
            expected_model_name = model_name

        elif expected_model_name != model_name:
            raise ValueError(f"All external IDs must belong to the same model, expected {expected_model_name}, got {model_name}")

        res_ids.append(int(res_id))

    if not expected_model_name or not res_ids:
        return []

    return res_ids
