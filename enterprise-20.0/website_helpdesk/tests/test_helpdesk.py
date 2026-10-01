import re

from odoo.tests.common import tagged, HttpCase, TransactionCase
from lxml import html


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestHelpdesk(HttpCase):
    def setUp(self):
        super().setUp()
        self.team_without_web_form = self.env['helpdesk.team'].create({
            'name': 'Team without Web Form',
            'is_published': True,
        })

    def test_create_ticket_portal(self):
        # Only one team has enabled the website form then Help website menu should open the Ticket Submit page
        # If that team has enabled Knowledge then it should open Knowledge page
        team = self.env['helpdesk.team'].search([('use_website_helpdesk_form', '=', True)], limit=1)
        self.env['helpdesk.team'].search([('id', '!=', team.id)]).use_website_helpdesk_form = False
        response = self.url_open('/helpdesk')
        self.assertEqual(response.status_code, 200)
        expected_string = "How can we help you?" if team.use_website_helpdesk_knowledge else "Submit a Ticket"
        search_result = re.search(expected_string.encode(), response.content).group().decode()
        self.assertEqual(search_result, expected_string)

        # multiple teams have enabled the website form then Help website menu should refere to the Team selection page
        self.team_without_web_form.use_website_helpdesk_form = True
        other_response = self.url_open('/helpdesk')
        self.assertEqual(response.status_code, 200)
        expected_string = "Select your Team for help"
        search_result = re.search(expected_string.encode(), other_response.content).group().decode()
        self.assertEqual(search_result, expected_string)

    def test_helpdesk_team_visibility(self):
        test_website = self.env['website'].create({'name': 'test website', 'sequence': 10})
        new_teams = [('Test team1', self.env.ref('base.default_website')),
                    ('Test team2', test_website),
                    ('Test team3', test_website)]
        for name, website in new_teams:
            self.env['helpdesk.team'].create([{
                'name': name,
                'use_website_helpdesk_form': True,
                'website_id': website.id,
                'is_published': True,
            }])
        response = self.url_open('/helpdesk')
        tree = html.fromstring(response.content)
        team_names = tree.xpath('//article[contains(@class, "team_card")]')

        self.assertEqual(len(team_names), 2, "Expected exactly 2 helpdesk teams to be rendered")


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestHelpdeskMenu(TransactionCase):
    def test_menu_item_visibility(self):
        website = self.env['website'].create({
            'name': 'test website'
        })
        public_user = self.env.ref('base.public_user')
        non_helpdesk_menu = self.env['website.menu'].create({
            'name': 'Menu with helpdesk in URL',
            'url': '/helpdesk-123',
            'website_id': website.id,
        })
        team = self.env['helpdesk.team'].create({
            'name': 'Test team',
            'use_website_helpdesk_form': True,
            'website_id': website.id,
        })

        non_helpdesk_menu.invalidate_recordset(["is_visible"])
        self.assertTrue(non_helpdesk_menu.with_user(public_user).is_visible, "Item with helpdesk in URL should stay visible.")
        self.assertTrue(team.website_menu_id.is_visible)
        team.use_website_helpdesk_form = False
        self.assertFalse(team.website_menu_id.is_visible)

    def test_ticket_base_url_uses_team_website(self):
        """ A ticket's base URL must follow its team's website, not the company default,
        so notification links target the website the ticket was created from. """
        websites = self.env['website'].create([
            {'name': 'W1', 'domain': 'https://w1.example.com', 'sequence': 1},
            {'name': 'W2', 'domain': 'https://w2.example.com', 'sequence': 2},
        ])
        team_w2 = self.env['helpdesk.team'].create({
            'name': 'Team W2',
            'use_website_helpdesk_form': True,
            'website_id': websites[1].id,
        })
        ticket = self.env['helpdesk.ticket'].create({
            'name': 'Test ticket',
            'team_id': team_w2.id,
        })
        self.assertEqual(ticket.get_base_url(), 'https://w2.example.com')

    def test_website_form_keeps_translations(self):
        """ The website form of a team must keep the template's translations, so
        it is rendered in the visitor's language regardless of the language of
        the user creating the team. """
        self.env['res.lang']._activate_lang('fr_FR')
        fr_lang = self.env['res.lang'].search([('code', '=', 'fr_FR')])
        website = self.env['website'].create({'name': 'French website'})
        website.write({'language_ids': [(4, fr_lang.id)], 'default_lang_id': fr_lang.id})

        # Translate the form title to French so the languages are distinguishable.
        submit_form = self.env.ref('website_helpdesk.ticket_submit_form')
        submit_form.update_field_translations('arch_db', {'fr_FR': {'Submit a Ticket': 'Soumettre un ticket'}})

        # The user configuring the team uses English while the website is French.
        team = self.env['helpdesk.team'].with_context(lang='en_US').create({
            'name': 'French Team',
            'use_website_helpdesk_form': True,
            'website_id': website.id,
        })

        form_view = team.website_form_view_id
        self.assertIn('Submit a Ticket', form_view.with_context(lang='en_US').arch,
            "The generated form should keep its English translation.")
        self.assertIn('Soumettre un ticket', form_view.with_context(lang='fr_FR').arch,
            "The generated form should keep its French translation.")

    def test_archive_multiple_teams_different_websites(self):
        """ Test archiving multiple helpdesk teams linked to different websites. """
        websites = self.env['website'].create([{'name': 'W1'}, {'name': 'W2'}])

        teams = self.env['helpdesk.team'].create([{
            'name': f'Team of {website.name}',
            'use_website_helpdesk_form': True,
            'website_id': website.id,
        } for website in websites
        ])

        teams.write({'active': False})
        self.assertFalse(any(t.active for t in teams), "Both teams should be archived without errors.")

        # Verify that a website menu was created for each team and is linked to the correct website
        for i, team in enumerate(teams):
            self.assertTrue(team.website_menu_id and team.website_menu_id.exists(), f"Expected a website menu to be created for {team.name}")
            self.assertEqual(team.website_menu_id.website_id, websites[i])
        self.assertNotEqual(teams[0].website_menu_id.id, teams[1].website_menu_id.id, "Each team should have its own distinct menu")

    def _create_teams(self, names, website, **extra_vals):
        single = isinstance(names, str)
        name_list = [names] if single else names
        vals_list = [
            {'name': name, 'use_website_helpdesk_form': True, 'website_id': website.id, **extra_vals}
            for name in name_list
        ]
        teams = self.env['helpdesk.team'].create(vals_list)
        return teams[0] if single else teams

    def test_website_menu_sharing_and_cleanup(self):
        """
        Test scenarios for shared helpdesk Help menus:
        - reuse on team creation
        - reuse with a custom menu URL
        - cleanup once no team references the menu anymore.
        - when archiving the last team on a website, the menu should present.
        """
        website = self.env['website'].create({'name': 'Test Website'})

        # Creating a new team should not create a new Help menu; it should reuse the existing one.
        team_a = self._create_teams('Team A', website)
        self.assertTrue(team_a.website_menu_id, "First team should have a website menu.")
        team_b = self._create_teams('Team B', website)
        self.assertEqual(team_b.website_menu_id, team_a.website_menu_id,
                          "Second team should reuse the existing menu, not create a new one.")

        # A custom menu URL should not prevent it from being reused.
        team_a.website_menu_id.write({'name': 'Support', 'url': '/support'})
        team_c = self._create_teams('Team C', website)
        self.assertEqual(team_c.website_menu_id, team_a.website_menu_id,
                          "Renaming the menu should not prevent it from being reused.")

        # Unlinking the last team referencing the menu removes it.
        menu = team_a.website_menu_id
        (team_a + team_b + team_c).unlink()
        self.assertFalse(menu.exists(), "Menu should be removed once no team references it anymore.")

        # Archiving the only team on a website keeps the menu for the next team to reuse.
        team_d = self._create_teams('Team D', website)
        team_d.active = False
        team_e = self._create_teams('Team E', website)
        self.assertEqual(team_e.website_menu_id, team_d.website_menu_id,
                          "New team should reuse the archived team's menu instead of duplicating it.")
