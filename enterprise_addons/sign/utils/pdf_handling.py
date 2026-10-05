# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from io import BytesIO

from odoo.exceptions import ValidationError
from odoo.tools.pdf import DependencyError, errors, NameObject, PdfFileReader, PdfFileWriter, PdfReadError, NumberObject, DictionaryObject
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)
_logger = logging.getLogger(__name__)


def get_valid_pdf_data(pdf_bytes, strict=True):
    """
    Validate and return a readable PDF file object from the given byte data.

    :param pdf_bytes: Raw byte data of the PDF file to be validated.
    :param strict: Enforce strict parsing of the PDF file.
    :return: A valid and non-encrypted PdfFileReader instance.
    :raises ValidationError: If cannot return non-encrypted PdfFileReader instance.
    """
    # If strict=True is explicitly requested, try strict first then fall back to lenient.
    # By default we favor lenient parsing to cope with malformed yet readable PDFs.
    # pypdf strict=False enables best-effort parsing for PDFs that don't follow the spec exactly.
    # See https://pypdf.readthedocs.io/en/stable/user/robustness.html
    strict_modes = (strict, False) if strict else (False,)
    for strict_flag in strict_modes:
        try:
            pdf_reader = PdfFileReader(BytesIO(pdf_bytes), strict_flag)
            if pdf_reader.is_encrypted:
                continue
            if strict_flag is False and strict:
                _logger.warning("Strict PDF parsing failed; falling back to lenient mode.")
            return pdf_reader
        except (DependencyError, UnicodeDecodeError, PdfReadError):
            _logger.warning("Failed to read PDF data (strict=%s).", strict_flag, exc_info=True)
            continue

    # FIXME this will probably fail because language is not resolved
    raise ValidationError(_lt(
        "It seems that we're not able to process one of the uploaded pdf. It is either"
        " encrypted, or encoded in a format we do not support."
    ))


# TODO: Wait for the next Debian release to bump the pypdf dependency to >= 5.8.0.
#  Starting from pypdf 5.8.0, true annotation flattening is natively supported. Once upgraded,
#  this can be replaced with real PDF flattening using the  function `update_page_form_field_values`
def lock_pdf_interactive_forms(pdf_bytes):
    """
    Makes a PDF non-editable by locking all interactive form fields to Read-Only.

    This function locks the data and UI layers of the
    widgets so the user cannot alter the values.

    :param pdf_bytes: Raw byte data of the PDF file
    :return: Flattened, non-editable PDF.
    :raises ValidationError: If the PDF cannot be decoded or parsed.
    """
    try:
        pdf_reader = get_valid_pdf_data(pdf_bytes)

        # Check if the PDF is signed before locking the fields to avoid invalidating the signature
        form_fields = pdf_reader.get_fields() or {}
        for field in form_fields.values():
            if field.get("/FT") == "/Sig":
                return pdf_bytes

        output_pdf = PdfFileWriter()
        output_pdf.append_pages_from_reader(pdf_reader)

        for page in output_pdf.pages:
            if "/Annots" in page:
                for annot_ref in page["/Annots"]:
                    annot_obj = annot_ref.get_object()

                    # If the annotation is an interactive form Widget
                    if annot_obj.get("/Subtype") == "/Widget":
                        if "/FT" in annot_obj and "/T" in annot_obj:
                            parent_annot_obj = annot_obj
                        else:
                            parent_annot_obj = annot_obj.get("/Parent", DictionaryObject()).get_object()

                        # Bit 1 (Value 1) = Read-Only Data
                        current_ff = parent_annot_obj.get("/Ff", 0)
                        parent_annot_obj[NameObject("/Ff")] = NumberObject(current_ff | 1)

    except errors.PyPdfError as e:
        _logger.warning("Failed to parse PDF during locking interactive widgets: %s", e)
        return pdf_bytes

    output_stream = BytesIO()
    output_pdf.write(output_stream)
    return output_stream.getvalue()
