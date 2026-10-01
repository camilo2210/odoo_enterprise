# Part of Odoo. See LICENSE file for full copyright and licensing details.

from functools import reduce

from odoo import Command
from odoo.tests.common import TransactionCase


class TestResPartner(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Documents, Partner = cls.env['documents.document'], cls.env['res.partner']
        root = Partner.create({
            'name': 'A',
            'child_ids': [
                Command.create({'name': 'AA'}),
                Command.create({'name': 'AB', 'child_ids': [Command.create({'name': 'ABA'})]}),
                Command.create({'name': 'AC', 'child_ids': [Command.create({'name': 'ACA'})]}),
            ]
        })
        cls.partners = Partner.search([('id', 'child_of', root.ids)]) | Partner.create({'name': 'no_hierarchy'})
        cls.partner_by_name = cls.partners.grouped('name')
        cls.docs_per_partner = Documents.create(
            [{'name': partner.name, 'raw': b'', 'partner_id': partner.id}
             for partner in cls.partners]).grouped('partner_id')
        cls.partner_by_name['ABA'].active = False

    def test_document_count(self):
        """Test document_count compute method."""
        self.partners.mapped('document_count')  # Compute document_count in batch
        self.assertEqual(self.partner_by_name['A'].document_count, 6)
        self.assertEqual(self.partner_by_name['AA'].document_count, 1)
        self.assertEqual(self.partner_by_name['AB'].document_count, 2)
        self.assertEqual(self.partner_by_name['ABA'].document_count, 1)
        self.assertEqual(self.partner_by_name['no_hierarchy'].document_count, 1)

    def test_document_count_performance(self):
        """Test the performance of document_count compute method (as we don't explicitly prefetch the parent_id)."""
        self.env.invalidate_all()
        with self.assertQueryCount(__system__=3):
            self.partners.mapped('document_count')

    def test_documents_action_see_domain(self):
        """Test the domain returned by action_see_documents method."""
        Documents = self.env['documents.document']
        documents_in_hierarchy = reduce(
            lambda a, b: a | b,
            [self.docs_per_partner[self.partner_by_name[pname]] for pname in ('A', 'AA', 'AB', 'ABA', 'AC', 'ACA')])
        self.assertEqual(
            Documents.search(self.partner_by_name['A'].action_see_documents()['domain']), documents_in_hierarchy)
        self.assertEqual(
            Documents.search(self.partner_by_name['AB'].action_see_documents()['domain']),
            self.docs_per_partner[self.partner_by_name['AB']] | self.docs_per_partner[self.partner_by_name['ABA']])
        self.assertEqual(
            Documents.search(self.partner_by_name['AA'].action_see_documents()['domain']),
            self.docs_per_partner[self.partner_by_name['AA']])
        self.partner_by_name['A'].active = False
        self.assertEqual(
            Documents.search(self.partner_by_name['A'].action_see_documents()['domain']), documents_in_hierarchy)
