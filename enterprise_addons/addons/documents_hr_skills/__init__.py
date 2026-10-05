from . import models


def _post_init_hook(env):
    """Post-init hook to create the Certificate subfolder for the already created employees."""
    env['hr.employee'].search([])._generate_employee_certificate_folder()
