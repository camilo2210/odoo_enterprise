# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HelpdeskTeam(models.Model):
    _name = 'helpdesk.team'
    _inherit = ['helpdesk.team', 'website.published.mixin', 'website.seo.metadata', 'image.mixin']

    feature_form_url = fields.Char('URL to Submit Issue', readonly=True, compute='_compute_form_url', export_string_translation=False)
    website_id = fields.Many2one('website', domain="[('company_id', '=?', company_id)]", compute='_compute_website_id', store=True, readonly=False)
    website_menu_id = fields.Many2one('website.menu', export_string_translation=False)
    website_form_view_id = fields.Many2one('ir.ui.view', export_string_translation=False)

    @api.constrains('use_website_helpdesk_form', 'website_id', 'company_id')
    def _check_website_company(self):
        if any(t.use_website_helpdesk_form and t.website_id and t.website_id.company_id != t.company_id for t in self):
            raise ValidationError(_('The companies of the team and the website should match.'))

    @api.depends('company_id')
    def _compute_website_id(self):
        for team in self:
            team.website_id = team.company_id.website_id

    @api.model
    def _get_knowledge_base_fields(self):
        return []

    @api.depends(lambda self: ['use_website_helpdesk_form'] + [f for f in self._get_knowledge_base_fields()])
    def _compute_show_knowledge_base(self):
        kb_fields = self._get_knowledge_base_fields()
        for team in self:
            team.show_knowledge_base = team.use_website_helpdesk_form and any(team[field] for field in kb_fields)

    def _compute_website_url(self):
        super()._compute_website_url()
        for team in self:
            team.website_url = "/helpdesk/%s" % self.env['ir.http']._slug(team)

    @api.onchange('use_website_helpdesk_form', 'use_website_helpdesk_forum', 'use_website_helpdesk_slides', 'use_website_helpdesk_knowledge')
    def _onchange_use_website_helpdesk(self):
        if not (self.use_website_helpdesk_form or self.use_website_helpdesk_forum or self.use_website_helpdesk_slides or self.use_website_helpdesk_knowledge) and self.website_published:
            self.is_published = False
        elif self.use_website_helpdesk_form and not self.website_published:
            self.is_published = True

    def write(self, vals):
        if 'active' in vals and not vals['active']:
            vals['is_published'] = False
        res = super().write(vals)
        if 'use_website_helpdesk_form' in vals and vals['use_website_helpdesk_form']:
            self._ensure_submit_form_view()
        if {'use_website_helpdesk_form', 'is_published'} & vals.keys():
            self._ensure_website_menu()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        teams = super().create(vals_list)
        teams.filtered('use_website_helpdesk_form')._ensure_submit_form_view()
        teams._ensure_website_menu()
        return teams

    def unlink(self):
        self._unlink_unused_menus()
        return super().unlink()

    def _unlink_unused_menus(self):
        """Remove the website menus of `self` that no other team (active or
        archived) still relies on, since a menu can be shared by several teams
        on the same website.

        When called with the `include_reusable_teams` context key, also
        returns the other teams currently pointing to a website menu, so
        `_ensure_website_menu` can reuse an existing menu for `self`'s website
        instead of creating a duplicate.
        """
        menus = self.website_menu_id
        include_reusable_teams = self.env.context.get('include_reusable_teams')
        if not menus and not include_reusable_teams:
            return

        domain = [
            ('use_website_helpdesk_form', '=', True),
            ('id', 'not in', self.ids),
        ]
        # if we have menus to check, only look at teams using those menus.
        # otherwise, we're just looking for any menu to reuse, so fetch all teams that have one.
        domain.append(('website_menu_id', 'in', menus.ids) if menus else ('website_menu_id', '!=', False))
        other_teams_with_menu = self.env['helpdesk.team'].sudo().with_context(active_test=False).search(domain)

        if menus:
            (menus - other_teams_with_menu.website_menu_id).unlink()
        if include_reusable_teams:
            return other_teams_with_menu

    def _ensure_submit_form_view(self):
        teams = self.filtered('use_website_helpdesk_form')
        if not teams:
            return

        submit_form = self.env.ref('website_helpdesk.ticket_submit_form').sudo()
        for team in teams:
            if not team.website_form_view_id:
                xmlid = 'website_helpdesk.team_form_' + str(team.id)
                form_template = submit_form.copy({'name': xmlid, 'key': xmlid})
                self.env['ir.model.data'].sudo().create({
                    'module': 'website_helpdesk',
                    'name': xmlid.split('.')[1],
                    'model': 'ir.ui.view',
                    'res_id': form_template.id,
                    'noupdate': True
                })
                team.website_form_view_id = form_template.id

    def _ensure_website_menu(self):
        teams_with_form_enabled = self.filtered_domain([('use_website_helpdesk_form', '=', True)])
        teams_with_form_disabled = self - teams_with_form_enabled
        teams_needing_menu = teams_with_form_enabled.filtered(lambda team: not team.website_menu_id)

        # nothing to release and nothing to assign: e.g. archiving a team that
        # already owns its menu, or duplicating one whose menu got copied along
        if not teams_with_form_disabled.website_menu_id and not teams_needing_menu:
            return

        other_teams_with_menu = teams_with_form_disabled.with_context(
            include_reusable_teams=True
        )._unlink_unused_menus()
        teams_with_form_disabled.website_menu_id = False

        teams_with_menu_by_website = other_teams_with_menu.grouped('website_id')
        for website, teams in teams_needing_menu.grouped('website_id').items():
            parent_menu = website.menu_id
            if not parent_menu:
                continue

            team_with_existing_menu = teams_with_menu_by_website.get(website)
            if team_with_existing_menu:
                menu = team_with_existing_menu[:1].website_menu_id
            else:
                menu = self.env['website.menu'].sudo().create({
                    'name': _('Help'),
                    'url': '/helpdesk',
                    'parent_id': parent_menu.id,
                    'sequence': 50,
                    'website_id': website.id,
                })
            teams.website_menu_id = menu.id

    @api.depends('name', 'use_website_helpdesk_form', 'company_id')
    def _compute_form_url(self):
        for team in self:
            base_url = team.get_base_url()
            team.feature_form_url = (team.use_website_helpdesk_form and team.name and team.id) and (base_url + '/helpdesk/' + self.env['ir.http']._slug(team)) or False

    def _helpcenter_filter_types(self):
        return {}

    def _helpcenter_filter_tags(self, search_type):
        return []

    def _helpcenter_date_from_search(self, searches):
        if not searches.get('date'):
            return False

        delta = {'7days': 7, '30days': 30, '365days': 365}.get(searches['date'])
        if not delta:
            return False

        today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        return today - timedelta(days=delta)

    def get_knowledge_base_url(self):
        self.ensure_one()
        return self.feature_form_url

    def _get_search_options(self, searches):
        return {
            'allowFuzzy': True,
            'helpdesk': self.env['ir.http']._slug(self),
            'max_date': self._helpcenter_date_from_search(searches),
            'tag': searches.get('tag', False),
        }

    def open_website_url(self):
        return self.env['website'].get_client_action(self.website_url, website_id=self.website_id.id)
