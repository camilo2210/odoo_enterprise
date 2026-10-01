from odoo import http
from odoo.http import request
from odoo.addons.website_hr_recruitment.controllers.main import WebsiteHrRecruitment


class HrWebsiteRecruitment(WebsiteHrRecruitment):

    def _capture_referral_data(self, **kwargs):
        """ Capture referral data from URL and store in the functional session across routes """
        utm_ref = kwargs.get('utm_reference')
        if utm_ref:
            request.session['hr_rec_utm_reference'] = utm_ref

    @http.route(['/jobs', '/jobs/page/<int:page>'])
    def jobs(self, **kwargs):
        self._capture_referral_data(**kwargs)
        return super().jobs(**kwargs)

    @http.route('''/jobs/<model("hr.job"):job>''')
    def job(self, job, **kwargs):
        self._capture_referral_data(**kwargs)
        return super().job(job, **kwargs)

    def extract_data(self, model_sudo, values):
        """
        Populate the hr.applicant record using session data.
        """
        data = super().extract_data(model_sudo, values)

        if model_sudo.model == "hr.applicant":
            ref_id = request.session.get('hr_rec_utm_reference')

            ref_user_id = None
            if ref_id:
                try:
                    str_id = str(ref_id).split(',')[-1]
                    ref_user_id = int(str_id)
                except (ValueError, IndexError, TypeError):
                    pass
            if ref_user_id:
                data['record']['ref_user_id'] = ref_user_id

        return data
