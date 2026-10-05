from . import controllers
from . import models
from . import report
from . import wizard


def uninstall_hook(env):
    # `relative_uom_id` cascades on delete: detach the core kWh unit that our
    # data re-based on our own J, or removing J would delete kWh along with it.
    kwh = env.ref('uom.product_uom_kwh')
    if kwh.relative_uom_id == env.ref('esg.product_uom_j'):
        kwh.write({'relative_factor': 1, 'relative_uom_id': False})
