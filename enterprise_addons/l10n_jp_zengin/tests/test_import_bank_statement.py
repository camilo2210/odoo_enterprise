# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


def zengin_file(*records, separator=b'\r\n'):
    """Build a Zengin file: every record is padded to the fixed 200 char width."""
    return separator.join(record.ljust(200) for record in records) + separator


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestImportZenginBankStatement(AccountTestInvoicingCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_country('jp')
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_journal = cls.company_data['default_journal_bank']

    def _import_zengin_file(self, name, raw):
        self.bank_journal.create_document_from_attachment(self.env['ir.attachment'].create({
            'mimetype': 'application/text',
            'name': name,
            'raw': raw,
        }).ids)
        return self.env['account.bank.statement'].search([('company_id', '=', self.env.company.id)])

    def test_zengin_transfer_file_import(self):
        # A UTF-8-encoded file is not valid SHIFT_JIS Zengin data, so importing it
        # must raise rather than silently produce a broken statement.
        zengin_transfer_utf8_file = (
            b'10100504050503240503310009\xef\xbe\x90\xef\xbe\x82\xef\xbd\xb2\xef\xbd\xbd\xef\xbe\x90\xef\xbe\x84\xef\xbe\x93        410\xef\xbd\xbb\xef\xbe\x9d\xef\xbe\x89\xef\xbe\x90\xef\xbe\x94          10355368\xef\xbe\x9c\xef\xbd\xb6\xef\xbd\xb8\xef\xbd\xbb\xef\xbd\xbc\xef\xbe\x96\xef\xbd\xb3\xef\xbd\xb6\xef\xbd\xb2                                                                                                                           \r\n'
            b'203000105032405032400000600000000000000          \xef\xbe\x9c\xef\xbd\xb6\xef\xbd\xb8\xef\xbd\xbb \xef\xbd\xb2\xef\xbe\x81\xef\xbe\x9b\xef\xbd\xb3                                       \xef\xbe\x90\xef\xbe\x82\xef\xbd\xb2\xef\xbd\xbd\xef\xbe\x90\xef\xbe\x84\xef\xbe\x93        \xef\xbd\xbb\xef\xbe\x9d\xef\xbe\x89\xef\xbe\x90\xef\xbe\x94                                                                                  \r\n'
            b'203000205032905032900000000000000000000          \xef\xbe\x9c\xef\xbd\xb6\xef\xbd\xb8\xef\xbd\xbb\xef\xbd\xbc\xef\xbe\x96\xef\xbd\xb3\xef\xbd\xbc\xef\xbe\x9e(\xef\xbd\xb6                                     \xef\xbe\x90\xef\xbe\x82\xef\xbd\xb2\xef\xbd\xbd\xef\xbe\x90\xef\xbe\x84\xef\xbe\x93        \xef\xbd\xbb\xef\xbe\x9d\xef\xbe\x89\xef\xbe\x90\xef\xbe\x94           050000000000000000000000                                               \r\n'
            b'8000002050000060000000000000000000000                                                                                                                                                                  \r\n9                                                                                                                                                                                                      \r\n')
        self.assertRaisesRegex(
            UserError,
            r"All or part of the following file\(s\) could not be imported",
            self._import_zengin_file,
            'zengin_transfer_utf8.txt',
            zengin_transfer_utf8_file,
        )

        zengin_transfer_file = zengin_file(
            b'10100504050503240503310009\xd0\xc2-\xb2\xbd\xd0\xc4\xd3       410\xbb\xdd\xc9\xd0\xd4          10355368\xdc\xb6\xb8\xbb\xbc\xd6\xb3\xb6\xb2                                                                                                                           ',
            b'203000105032405032400000600000000000000          \xdc\xb6\xb8\xbb \xb2\xc1\xdb\xb3                                       \xd0\xc2\xb2\xbd\xd0\xc4\xd3        \xbb\xdd\xc9\xd0\xd4                                                                                  ',
            b'203000205032905032900000000000000000000          \xdc\xb6\xb8\xbb\xbc\xd6\xb3\xbc\xde(\xb6                                     \xd0\xc2\xb2\xbd\xd0\xc4\xd3        \xbb\xdd\xc9\xd0\xd4           050000000000000000000000                                               ',
            b'8000002050000060000000000000000000000                                                                                                                                                                  ',
            b'9                                                                                                                                                                                                      ',
        )
        statement = self._import_zengin_file('zengin_transfer.txt', zengin_transfer_file)
        self.assertRecordValues(statement, [{
            'balance_start': 0.0,
            'balance_end_real': 50000060000.0,
        }])

    def test_zengin_deposit_withdrawal_file_import(self):
        zengin_deposit_withdrawal_file = zengin_file(
            b'10300504050503130503310009\xd0\xc2\xb2\xbd\xd0\xc4\xd3        410\xbb\xdd\xc9\xd0\xd4          00010000355368\xdc\xb6\xb8\xbb\xbc\xd6\xb3\xb6\xb2                               1100099028913211                                                                       ',
            b'203000001050313050313111000000060000000000000000                                 \xdc\xb6\xb8\xbb \xb2\xc1\xdb\xb3                                       \xd0\xc2\xb2\xbd\xd0\xc4\xd3        \xbb\xdd\xc9\xd0\xd4          \xcc\xd8\xba\xd0                                     ',
            b'203000002050331050331214000000005000000000000000                                                                                                               \xbf\xc9\xc0\xd6\xb7\xdd              0                    ',
            b'8000001000000006000000000100000000050001000990289132110000002                                                                                                                                           ',
            b'9000000001300001                                                                                                                                                                                       ',
        )
        statement = self._import_zengin_file('zengin_deposit_withdrawal.txt', zengin_deposit_withdrawal_file)
        self.assertRecordValues(statement, [{
            'balance_start': 99028913211.0,
            'balance_end_real': 99028968211.0,
        }])

    def test_zengin_transfer_file_import_without_separators(self):
        """
        Some banks export the file as one continuous string with no line
        separators. The parser must then fall back to fixed-width record
        chunking (200 chars) instead of choking on one oversized record.
        """
        zengin_transfer_file = zengin_file(
            b'10100504050503240503310009\xd0\xc2-\xb2\xbd\xd0\xc4\xd3       410\xbb\xdd\xc9\xd0\xd4          10355368\xdc\xb6\xb8\xbb\xbc\xd6\xb3\xb6\xb2                                                                                                                           ',
            b'203000105032405032400000600000000000000          \xdc\xb6\xb8\xbb \xb2\xc1\xdb\xb3                                       \xd0\xc2\xb2\xbd\xd0\xc4\xd3        \xbb\xdd\xc9\xd0\xd4                                                                                  ',
            b'203000205032905032900000000000000000000          \xdc\xb6\xb8\xbb\xbc\xd6\xb3\xbc\xde(\xb6                                     \xd0\xc2\xb2\xbd\xd0\xc4\xd3        \xbb\xdd\xc9\xd0\xd4           050000000000000000000000                                               ',
            b'8000002050000060000000000000000000000                                                                                                                                                                  ',
            b'9                                                                                                                                                                                                      ',
            separator=b'',
        )
        self.assertNotIn(b'\n', zengin_transfer_file)
        statement = self._import_zengin_file('zengin_transfer_no_sep.txt', zengin_transfer_file)
        self.assertEqual(len(statement.line_ids), 2, "Both transfer transactions should be imported")
        self.assertRecordValues(statement, [{
            'balance_start': 0.0,
            'balance_end_real': 50000060000.0,
        }])

    def test_zengin_deposit_withdrawal_file_import_without_separators(self):
        """
        Same continuous-string fallback for a deposit/withdrawal file.
        """
        zengin_deposit_withdrawal_file = zengin_file(
            b'10300504050503130503310009\xd0\xc2\xb2\xbd\xd0\xc4\xd3        410\xbb\xdd\xc9\xd0\xd4          00010000355368\xdc\xb6\xb8\xbb\xbc\xd6\xb3\xb6\xb2                               1100099028913211                                                                       ',
            b'203000001050313050313111000000060000000000000000                                 \xdc\xb6\xb8\xbb \xb2\xc1\xdb\xb3                                       \xd0\xc2\xb2\xbd\xd0\xc4\xd3        \xbb\xdd\xc9\xd0\xd4          \xcc\xd8\xba\xd0                                     ',
            b'203000002050331050331214000000005000000000000000                                                                                                               \xbf\xc9\xc0\xd6\xb7\xdd              0                    ',
            b'8000001000000006000000000100000000050001000990289132110000002                                                                                                                                           ',
            b'9000000001300001                                                                                                                                                                                       ',
            separator=b'',
        )
        self.assertNotIn(b'\n', zengin_deposit_withdrawal_file)
        statement = self._import_zengin_file('zengin_deposit_withdrawal_no_sep.txt', zengin_deposit_withdrawal_file)
        self.assertEqual(len(statement.line_ids), 2, "Both deposit/withdrawal transactions should be imported")
        self.assertRecordValues(statement, [{
            'balance_start': 99028913211.0,
            'balance_end_real': 99028968211.0,
        }])
