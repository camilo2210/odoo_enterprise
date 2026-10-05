from lxml import html
from markupsafe import Markup

from odoo import api, fields, models
from odoo.tools.urls import urljoin as url_join
from odoo.addons.mail.tools.parser import parse_res_ids


class EquityMailComposeMessage(models.TransientModel):
    _name = 'equity.mail.compose.message'
    _inherit = ['mail.composer.mixin']
    _description = "Equity Email composition wizard"

    model = fields.Char()
    res_ids = fields.Text()

    equity_button_text = fields.Char()
    equity_button_url = fields.Char()
    equity_button = fields.Html(compute='_compute_equity_button')

    author_id = fields.Many2one(
        comodel_name='res.partner',
        string="Author",
        required=True,
        default=lambda self: self.env.user.partner_id.id,
    )
    email_from = fields.Char(string="From", related='author_id.email')
    partner_ids = fields.Many2many('res.partner', string="Recipients", required=True)
    partner_ids_all_have_email = fields.Boolean(compute="_compute_partner_ids_all_have_email")

    @api.depends('template_id')
    def _compute_body(self):
        for composer in self:
            composer.body = self.env['ir.qweb']._render(html.fragment_fromstring(composer.template_id.body_html, create_parent='div'), {})

    def _get_equity_button_markup(self, partner=None):
        self.ensure_one()
        if self.equity_button_text and self.equity_button_url:
            return Markup("""
                <div style='padding-top: 10px;padding-bottom: 8px;'>
                    <a style='background-color: #875A7B;color: #FFFFFF;border-radius: 3px;text-align: center;font-size: 12px;padding: 8px 12px 11px;text-decoration: none !important;font-weight: bold;'
                       href='%(link)s?%(params)s'>
                        %(text)s
                    </a>
                </div>
                <hr>
            """) % {
                'link': url_join(self.get_base_url(), self.equity_button_url),
                'params': partner._get_equity_url_params() if partner else '',
                'text': self.equity_button_text,
            }
        else:
            return ''

    @api.depends_context('equity_url_text', 'equity_url_href')
    def _compute_equity_button(self):
        for wizard in self:
            wizard.equity_button = wizard._get_equity_button_markup()

    @api.depends('partner_ids')
    def _compute_partner_ids_all_have_email(self):
        for wizard in self:
            wizard.partner_ids_all_have_email = all(wizard.partner_ids.mapped('email'))

    def _get_full_mail_body(self, partner):
        self.ensure_one()
        return self._get_equity_button_markup(partner) + self.body

    def action_send_mail(self):
        self.ensure_one()

        def get_res_ids(partner):
            if self.model == 'equity.transaction':
                return parse_res_ids(self.res_ids, self.env)
            elif self.model == 'res.partner':
                return partner.ids

        for partner in self.partner_ids:
            self.env[self.model].browse(get_res_ids(partner)).with_context(recipient_name=partner.name).message_post(
                author_id=self.author_id.id,
                message_type='email_outgoing',
                subject=self.subject,
                body=self._get_full_mail_body(partner),
                email_layout_xmlid='equity.mail_notification_light',
                partner_ids=partner.ids,
            )
