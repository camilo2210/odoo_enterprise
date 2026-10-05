from odoo import api, models
from odoo.fields import Domain


class MailMessage(models.Model):
    _inherit = 'mail.message'

    @api.model
    def _message_fetch(self, domain, *, thread=None, **kwargs):
        """Filter payroll-sensitive messages from employee chatter."""
        if (
            thread
            and thread._name == 'hr.employee'
            and not self.env.user.has_group('hr_payroll.group_hr_payroll_user')
        ):
            payroll_subtype = self.env.ref(
                'hr_payroll.mt_hr_payroll_sensitive',
                raise_if_not_found=False,
            )
            if payroll_subtype:
                subtype_domain = Domain('subtype_id', '!=', payroll_subtype.id)
                domain = subtype_domain if domain is None else Domain(domain) & subtype_domain
        return super()._message_fetch(domain, thread=thread, **kwargs)
