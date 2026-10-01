from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.http import request
from odoo.addons.accountant_knowledge.controller.main import KnowledgeAuditReportController


class EsgReportController(KnowledgeAuditReportController):

    def _get_template_variables(self, article):
        if not (request.env.user.has_group('esg.esg_group_manager') and (esg_report := article.inherited_esg_report_id)):
            return super()._get_template_variables(article)

        data = esg_report._get_knowledge_report_data()
        return {f'{{{{ {k} }}}}': v for k, v in data.items()}

    def _get_html_template_variables(self, article):
        if not (
            request.env.user.has_group('esg.esg_group_manager')
            and (esg_report := article.inherited_esg_report_id)
            and esg_report.report_type == 'csrd'
        ):
            return super()._get_html_template_variables(article)

        actions_data = esg_report._get_knowledge_report_actions_data()
        rendered_actions = request.env['ir.qweb']._render('esg.esg_report_actions_table', actions_data) if actions_data.get('actions') else ''
        return {'{{ csrd_report_actions_global }}': rendered_actions}

    @http.route('/esg/article/<model("knowledge.article"):root_article>/esg_report', type='http', auth='user', methods=['GET'])
    def export_esg_article_to_pdf(self, root_article, include_pdf_files, include_child_articles, **kwargs):
        if not request.env.user.has_group('esg.esg_group_manager'):
            raise Forbidden()
        return super().export_article_to_pdf(root_article, include_pdf_files, include_child_articles, **kwargs)
