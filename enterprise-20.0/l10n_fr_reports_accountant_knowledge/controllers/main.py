from odoo import http
from odoo.addons.accountant_knowledge.controller.main import KnowledgeAuditReportController


class L10nFrKnowledgeAuditReportController(KnowledgeAuditReportController):
    def _get_template_variables(self, article):
        template_variables = super()._get_template_variables(article)
        fiscal_data = article._get_inherited_audit_report()._get_l10n_fr_knowledge_report_data()
        template_variables.update({f'{{{{ {name} }}}}': value for name, value in fiscal_data.items()})
        return template_variables

    @http.route()
    def export_article_to_pdf(self, root_article, include_pdf_files, include_child_articles, **kwargs):
        root_article._check_l10n_fr_attestation_selection(include_child_articles)
        return super().export_article_to_pdf(root_article, include_pdf_files, include_child_articles, **kwargs)
