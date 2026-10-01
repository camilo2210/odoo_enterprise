from lxml import html
from odoo import models
from odoo.exceptions import UserError


class KnowledgeArticle(models.Model):
    _inherit = 'knowledge.article'

    def _check_l10n_fr_attestation_selection(self, include_child_articles):
        self.ensure_one()
        attestation_template = self.env.ref('l10n_fr_reports_accountant_knowledge.l10n_fr_accountant_knowledge_article_template_attestation')
        attestation = self.search([
            ('id', 'child_of', self.id),
            ('origin_template_id', '=', attestation_template.id),
        ], limit=1)
        if not attestation or (attestation != self and include_child_articles != '1'):
            return

        fragment = html.fragment_fromstring(attestation.body, create_parent=True)
        if not fragment.xpath('''
            .//*[@data-embedded="foldableSection"
                and not(contains(concat(" ", normalize-space(@class), " "), " d-print-none "))]
        '''):
            raise UserError(self.env._('Select at least one attestation before printing the annual report.'))
