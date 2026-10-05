from . import models
from . import wizard


def _post_init_hook(env):
    companies = env['res.company'].search([])
    for field_name, xmlid in [
        ('wa_template_schedule_published', 'whatsapp_planning.whatsapp_template_planning_schedule_published'),
        ('wa_template_open_shift_available', 'whatsapp_planning.whatsapp_template_planning_open_shift_available'),
        ('wa_template_assigned_shift', 'whatsapp_planning.whatsapp_template_planning_assigned_shift'),
        ('wa_template_shift_reassigned', 'whatsapp_planning.whatsapp_template_planning_shift_reassigned'),
    ]:
        template = env.ref(xmlid)
        companies.filtered(
            lambda company: not template.wa_account_id or company in template.wa_account_id.allowed_company_ids
        ).write({field_name: template.id})
