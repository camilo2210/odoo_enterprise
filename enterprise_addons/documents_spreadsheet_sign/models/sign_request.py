import json
from odoo import models, fields
from odoo.exceptions import UserError
from odoo.tools.misc import format_datetime


class SignRequest(models.Model):
    _inherit = 'sign.request'

    def action_open_selected_requests_spreadsheet(self):
        """ Generate and open a spreadsheet for the selected signed requests.

        This method validates that a single template is selected and that the requests
        are signed. It then generates a spreadsheet document containing only the
        data from the selected requests.

        :return: The action to open the newly created spreadsheet.
        :rtype: dict
        :raise UserError: If multiple templates are selected or no requests are signed.
        """
        template = self.template_id
        if len(template) != 1:
            raise UserError(self.env._("You can only export one template at a time. \n Tip : group the list items by template"))
        signed_requests = self.filtered(lambda r: r.state == 'signed')
        if not signed_requests:
            raise UserError(self.env._("The sign request has not yet been signed by the signers"))
        spreadsheet_data = template._build_spreadsheet_data(sign_requests=signed_requests)
        folder = template._get_sign_answers_folder_sudo()
        datetime_str = format_datetime(self.env, fields.Datetime.now())

        action = self.env['documents.document'].sudo().action_open_new_spreadsheet({
            'name': f"{self.env._('Selected Answers: ')} {template.name} (#{template.id}) - {datetime_str}",
            'folder_id': folder.id,
            'spreadsheet_data': json.dumps(spreadsheet_data),
        })

        return action
