from . import models
from . import wizard


def _post_init_hook(env):
    report = env.ref("l10n_ro.tax_report", raise_if_not_found=False)
    if not report:
        return
    report.name = env._("VAT Report D300")
