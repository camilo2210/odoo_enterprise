from odoo.http import request
from odoo.addons.survey.controllers.main import Survey


class EsgMetricSurvey(Survey):
    def _check_validity(self, survey_sudo, answer_sudo, answer_token, ensure_token=True, check_partner=True):
        validity_code = super()._check_validity(survey_sudo, answer_sudo, answer_token, ensure_token, check_partner)

        if validity_code == 'answer_wrong_user' and answer_sudo and check_partner:
            if survey_sudo in request.env['esg.metric'].sudo().search([('survey_ids', '!=', False)]).survey_ids:
                user_partners = request.env['res.partner'].search([('user_id', '=', request.env.user.id)])
                partners = user_partners | request.env.user.partner_id
                if not request.env.user._is_public() and answer_sudo.partner_id in partners:
                    return True
        return validity_code

    def _get_access_data(self, survey_token, answer_token, ensure_token=True, check_partner=True):
        survey_sudo, answer_sudo = self._fetch_from_access_token(survey_token, answer_token)
        access_data = super()._get_access_data(survey_token, answer_token, ensure_token, check_partner)

        if survey_sudo and answer_sudo and access_data.get('validity_code', False) == 'answer_deadline' and request.env.user.has_group('esg.esg_group_manager'):
            if survey_sudo in request.env['esg.metric'].sudo().search([('survey_ids', '!=', False)]).survey_ids:
                # If the deadline is reached, ESG Manager should be able to consult answers
                access_data['can_answer'] = False
                access_data['validity_code'] = True
        return access_data
