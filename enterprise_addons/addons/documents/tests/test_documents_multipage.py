from unittest.mock import patch

from odoo.tests.common import TransactionCase

multipage_pdf = b"%PDF-1.3\n%\x93\x8c\x8b\x9e ReportLab Generated PDF document http://www.reportlab.com\n1 0 obj\n<<\n/F1 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/BaseFont /Helvetica /Encoding /WinAnsiEncoding /Name /F1 /Subtype /Type1 /Type /Font\n>>\nendobj\n3 0 obj\n<<\n/Contents 8 0 R /MediaBox [ 0 0 595.2756 841.8898 ] /Parent 7 0 R /Resources <<\n/Font 1 0 R /ProcSet [ /PDF /Text /ImageB /ImageC /ImageI ]\n>> /Rotate 0 /Trans <<\n\n>> \n  /Type /Page\n>>\nendobj\n4 0 obj\n<<\n/Contents 9 0 R /MediaBox [ 0 0 595.2756 841.8898 ] /Parent 7 0 R /Resources <<\n/Font 1 0 R /ProcSet [ /PDF /Text /ImageB /ImageC /ImageI ]\n>> /Rotate 0 /Trans <<\n\n>> \n  /Type /Page\n>>\nendobj\n5 0 obj\n<<\n/PageMode /UseNone /Pages 7 0 R /Type /Catalog\n>>\nendobj\n6 0 obj\n<<\n/Author (anonymous) /CreationDate (D:20230315150642-01'00') /Creator (ReportLab PDF Library - www.reportlab.com) /Keywords () /ModDate (D:20230315150642-01'00') /Producer (ReportLab PDF Library - www.reportlab.com) \n  /Subject (unspecified) /Title (untitled) /Trapped /False\n>>\nendobj\n7 0 obj\n<<\n/Count 2 /Kids [ 3 0 R 4 0 R ] /Type /Pages\n>>\nendobj\n8 0 obj\n<<\n/Filter [ /ASCII85Decode /FlateDecode ] /Length 59\n>>\nstream\nGapQh0E=F,0U\\H3T\\pNYT^QKk?tc>IP,;W#U1^23ihPEM_PP$O!3^,C5Q~>endstream\nendobj\n9 0 obj\n<<\n/Filter [ /ASCII85Decode /FlateDecode ] /Length 59\n>>\nstream\nGapQh0E=F,0U\\H3T\\pNYT^QKk?tc>IP,;W#U1^23ihPEM_PP$O!3^,C5Q~>endstream\nendobj\nxref\n0 10\n0000000000 65535 f \n0000000073 00000 n \n0000000104 00000 n \n0000000211 00000 n \n0000000414 00000 n \n0000000617 00000 n \n0000000685 00000 n \n0000000981 00000 n \n0000001046 00000 n \n0000001194 00000 n \ntrailer\n<<\n/ID \n[<ae91d9eb665e71f8931a929628e033c2><ae91d9eb665e71f8931a929628e033c2>]\n% ReportLab generated PDF document -- digest (http://www.reportlab.com)\n\n/Info 6 0 R\n/Root 5 0 R\n/Size 10\n>>\nstartxref\n1342\n%%EOF\n"
single_page_pdf = b"%PDF-1.3\n%\x93\x8c\x8b\x9e ReportLab Generated PDF document http://www.reportlab.com\n1 0 obj\n<<\n/F1 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/BaseFont /Helvetica /Encoding /WinAnsiEncoding /Name /F1 /Subtype /Type1 /Type /Font\n>>\nendobj\n3 0 obj\n<<\n/Contents 7 0 R /MediaBox [ 0 0 595.2756 841.8898 ] /Parent 6 0 R /Resources <<\n/Font 1 0 R /ProcSet [ /PDF /Text /ImageB /ImageC /ImageI ]\n>> /Rotate 0 /Trans <<\n\n>> \n  /Type /Page\n>>\nendobj\n4 0 obj\n<<\n/PageMode /UseNone /Pages 6 0 R /Type /Catalog\n>>\nendobj\n5 0 obj\n<<\n/Author (anonymous) /CreationDate (D:20230315151051-01'00') /Creator (ReportLab PDF Library - www.reportlab.com) /Keywords () /ModDate (D:20230315151051-01'00') /Producer (ReportLab PDF Library - www.reportlab.com) \n  /Subject (unspecified) /Title (untitled) /Trapped /False\n>>\nendobj\n6 0 obj\n<<\n/Count 1 /Kids [ 3 0 R ] /Type /Pages\n>>\nendobj\n7 0 obj\n<<\n/Filter [ /ASCII85Decode /FlateDecode ] /Length 59\n>>\nstream\nGapQh0E=F,0U\\H3T\\pNYT^QKk?tc>IP,;W#U1^23ihPEM_PP$O!3^,C5Q~>endstream\nendobj\nxref\n0 8\n0000000000 65535 f \n0000000073 00000 n \n0000000104 00000 n \n0000000211 00000 n \n0000000414 00000 n \n0000000482 00000 n \n0000000778 00000 n \n0000000837 00000 n \ntrailer\n<<\n/ID \n[<0d67aed8350bdb5b4bacc90e918480cb><0d67aed8350bdb5b4bacc90e918480cb>]\n% ReportLab generated PDF document -- digest (http://www.reportlab.com)\n\n/Info 5 0 R\n/Root 4 0 R\n/Size 8\n>>\nstartxref\n985\n%%EOF\n"


class TestMultipage(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.folder_a = cls.env['documents.document'].create({
            'name': 'folder A',
            'type': 'folder',
        })

    def test_multipage_pdfs_documents(self):
        document = self.env['documents.document'].create({
            'name': 'multipage.pdf',
            'mimetype': 'application/pdf',
            'raw': multipage_pdf,
            'folder_id': self.folder_a.id,
        })
        self.assertTrue(document.is_multipage)

    def test_single_page_pdfs_documents(self):
        document = self.env['documents.document'].create({
            'name': 'single_page.pdf',
            'mimetype': 'application/pdf',
            'raw': single_page_pdf,
            'folder_id': self.folder_a.id,
        })
        self.assertFalse(document.is_multipage)

    def test_unhandled_url_type_pdfs(self):
        attachment = self.env['ir.attachment'].create({
            'name': 'remote_document',
            'type': 'url',
            'url': 'https://example.com/document.pdf',
            'mimetype': 'application/pdf',
        })
        document = self.env['documents.document'].create({
            'name': 'url_type_document',
            'attachment_id': attachment.id,
        })
        with patch("odoo.addons.documents.models.documents_document._logger.warning") as mock_logging_warning:
            self.assertIsNone(document._get_is_multipage())
        mock_logging_warning.assert_not_called()
