from lxml import html

from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged('-at_install', 'post_install')
class TestHelpdeskSlidesForum(HttpCase):

    def test_helpdesk_forums_page_multiple_forums(self):
        """
        Test multiple forums should render linked to single helpdesk team.
        """
        first_forum, second_forum = self.env['forum.forum'].create([
            {
                'name': 'First Forum',
                'privacy': 'public',
            },
            {
                'name': 'Second Forum',
                'privacy': 'public',
            }
        ])

        helpdesk_team = self.env['helpdesk.team'].create({
            'name': 'Test Team',
            'website_forum_ids': [Command.set((first_forum | second_forum).ids)],
            'website_published': True,
        })

        response = self.url_open(url=f"/helpdesk/{self.env['ir.http']._slug(helpdesk_team)}/forums")
        self.assertEqual(
            response.status_code, 200,
            'Forums listing page should render successfully for a team with multiple forums.'
        )
        self.assertIn(first_forum.name, response.text)
        self.assertIn(second_forum.name, response.text)

    def test_helpdesk_forums_page_course_linked_forum(self):
        """
        A forum linked to an eLearning course is rendered through a different
        branch than a plain forum (see website_slides_forum's split of
        website_forum.forum_all into "regular" vs "course" forum groups).
        The helpdesk listing must not invite visitors to "/slides" from
        either branch.
        """
        plain_forum, course_forum = self.env['forum.forum'].create([
            {
                'name': 'Plain Forum',
                'privacy': 'public',
            },
            {
                'name': 'Linked Forum',
                'privacy': 'public',
            }
        ])
        self.env['slide.channel'].create({
            'name': 'Test Course',
            'forum_id': course_forum.id,
            'website_published': True,
        })

        helpdesk_team = self.env['helpdesk.team'].create({
            'name': 'Test Team',
            'website_forum_ids': [Command.set((plain_forum | course_forum).ids)],
            'website_published': True,
        })

        response = self.url_open(url=f"/helpdesk/{self.env['ir.http']._slug(helpdesk_team)}/forums")
        self.assertEqual(response.status_code, 200)
        self.assertIn(plain_forum.name, response.text)
        self.assertIn(course_forum.name, response.text)

        forums_list = html.fromstring(response.content).get_element_by_id('o_wforum_forums_index_list')
        self.assertFalse(
            forums_list.xpath(".//a[@href='/slides']"),
            'The helpdesk forums listing should not link to /slides, even for a course-linked forum.'
        )
        badge_cards = forums_list.xpath(".//a[div[contains(@class, 'badge')]]")
        self.assertEqual(
            len(badge_cards), 1,
            'Exactly one forum card (the course-linked one) should show the "Course" badge.'
        )
        self.assertIn(
            course_forum.name, badge_cards[0].text_content(),
            'The "Course" badge is a plain visual indicator (no navigation) and should still be shown, '
            'and only on the course-linked forum.'
        )
