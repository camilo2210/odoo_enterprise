import base64
import io
from collections import defaultdict
import logging
import textwrap

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo.tools import BinaryBytes, file_open, file_path, format_date, html_escape
from odoo.tools.image import image_data_uri
from odoo.tools.pdf import PdfFileReader, PdfReadError, reshape_text
from odoo.addons.sign.utils.pdf_handling import get_valid_pdf_data

from PIL import UnidentifiedImageError

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.pdfbase.ttfonts import TTFError

_logger = logging.getLogger()

DEFAULT_FONTS = [
    "NotoSans-Regular",
    "NotoSansArabic-Regular",
    "NotoSansBengali-Regular",
    "NotoSansDevanagari-Regular",
    "NotoSansGurmukhi-Regular",
]

DEFAULT_FONT_FILES = []
for font in DEFAULT_FONTS:
    try:
        path = file_path(f"web/static/fonts/sign/{font}.ttf")
        DEFAULT_FONT_FILES.append(path)
    except (FileNotFoundError, ValueError) as e:
        _logger.warning(
            "Font file %s.ttf not found, skipping. Error: %s",
            font,
            e,
        )


DRAWN_AREA_MARGIN = 2  # extra points kept around what a sign item drew, so no glyph edge is ever cut off


def _annotation_rect(can, drawn_areas):
    """
    Calculates the bounding rectangle for a sign item in page coordinates.

    The rectangle includes all drawn areas plus a margin to ensure nothing is cut off.
    It uses the canvas (``can``) to accurately map these areas to the page, which
    automatically handles page rotation.

    :param can: The canvas the sign item was drawn on.
    :param drawn_areas: The areas drawn by the item, given as ``(x0, y0, x1, y1)`` canvas coordinates.
    :returns: A tuple representing the bounding rectangle in page coordinates.
    """
    corners = [
        can.absolutePosition(x, y)
        for x in (min(area[0] for area in drawn_areas), max(area[2] for area in drawn_areas))
        for y in (min(area[1] for area in drawn_areas), max(area[3] for area in drawn_areas))
    ]

    return (
        min(x for x, _y in corners) - DRAWN_AREA_MARGIN,
        min(y for _x, y in corners) - DRAWN_AREA_MARGIN,
        max(x for x, _y in corners) + DRAWN_AREA_MARGIN,
        max(y for _x, y in corners) + DRAWN_AREA_MARGIN,
    )


def _fix_image_transparency(image):
    """ Modify image transparency to minimize issue of grey bar artefact.
    When an image has a transparent pixel zone next to white pixel zone on a
    white background, this may cause on some renderer grey line artefacts at
    the edge between white and transparent.

    This method sets black transparent pixel to white transparent pixel which solves
    the issue for the most probable case. With this the issue happen for a
    black zone on black background but this is less likely to happen.
    """
    pixels = image.load()
    for x in range(image.size[0]):
        for y in range(image.size[1]):
            if pixels[x, y] == (0, 0, 0, 0):
                pixels[x, y] = (255, 255, 255, 0)


class SignDocument(models.Model):
    _name = 'sign.document'
    _description = 'Signature Document'
    _order = 'sequence'
    # A document is a PDF plus its sign items, so merging two would lose one of the PDFs.
    _prevent_merge = True
    _disable_data_merge = True

    sequence = fields.Integer()
    attachment_id = fields.Many2one('ir.attachment', string="Attachment", required=True, index=True, ondelete='restrict')
    raw = fields.Binary(related='attachment_id.raw', readonly=False)
    name = fields.Char('Name', related='attachment_id.name', readonly=False)
    template_id = fields.Many2one('sign.template', 'Template', index=True, ondelete='cascade', required=True)
    sign_item_ids = fields.One2many('sign.item', 'document_id', string="Signature Items", copy=True)
    num_pages = fields.Integer('Number of pages', compute="_compute_num_pages", readonly=True, store=True)

    @api.depends('attachment_id.raw')
    def _compute_num_pages(self):
        for record in self:
            try:
                record.num_pages = self._get_pdf_number_of_pages(record.attachment_id.raw) or 0
            except (ValueError, ValidationError):
                record.num_pages = 0

    @api.model_create_multi
    def create(self, vals_list):
        attachments = self.env['ir.attachment'].browse([vals.get('attachment_id') for vals in vals_list if vals.get('attachment_id')])
        for attachment in attachments:
            self._check_pdf_data_validity(attachment.raw)
        for vals, attachment in zip(vals_list, attachments):
            if attachment.res_model or attachment.res_id:
                vals['attachment_id'] = attachment.copy().id
            else:
                attachment.res_model = self._name
        documents = super().create(vals_list)
        default_name = self.env['sign.template'].default_get(fields=['name'])['name']
        for document, attachment in zip(documents, documents.attachment_id):
            attachment.write({
                'res_model': self._name,
                'res_id': document.id
            })
            if document.template_id.name == default_name:
                document.template_id.name = document.name
        documents.attachment_id.check_access('read')
        return documents

    @api.model
    def create_from_attachment_data(self, attachment_data_list, template_id):
        """
        Create sign.document records from a list of dictionaries containing attachment data.

        :param attachment_data_list: List of dictionaries, each with 'name' and 'raw' keys.
                                     Example: [{'name': 'asdf', 'raw': 'asdfasdfasdf23423'}, ...]
        :return: List the newly created sign.document records.
        :raises UserError: If the input list is empty or a dictionary is missing required keys.
        """
        if not attachment_data_list:
            raise UserError(self.env._("The attachment data list cannot be empty."))
        attachments = self.env['ir.attachment'].create([
            {
                k: v
                for k, v in data.items()
                if k in ('name', 'raw')
            }
            for data in attachment_data_list
        ])
        return self.create([
            {
                'attachment_id': attachment.id,
                'sequence': data['sequence'],
                'template_id': template_id,
            }
            for data, attachment in zip(attachment_data_list, attachments, strict=True)
        ])

    def write(self, vals):
        res = super().write(vals)
        if 'attachment_id' in vals:
            self.attachment_id.check_access('read')
        return res

    @api.onchange("attachment_id")
    def _onchange_attachment_id(self):
        self.attachment_id.check_access('read')

    def get_radio_sets_dict(self):
        """
        :return: dict radio_sets_dict that maps each radio set that belongs to
            this template to a dictionary containing num_options and radio_item_ids.
        """
        radio_sets = self.sign_item_ids.filtered(lambda item: item.radio_set_id).radio_set_id
        radio_sets_dict = {
            radio_set.id: {
                'num_options': radio_set.num_options,
                'radio_item_ids': radio_set.radio_items.ids,
            } for radio_set in radio_sets
        }
        return radio_sets_dict

    def _get_sign_items_by_page(self):
        self.ensure_one()
        items = defaultdict(lambda: self.env['sign.item'])
        for item in self.sign_item_ids:
            items[item.page] += item
        return items

    def update_attachment_name(self, name):
        """
        Updates the attachment's name. If the provided name is empty or None,
        the current name is retained. This forced update prevents the creation
        of duplicate sign items during simultaneous RPC requests.

        :param name: The new name for the attachment.
        :return:

            - True: Indicates the attachment name was successfully updated.
            - False: Indicates the update was skipped because a sign request linked
              to the template already exists
        """
        self.ensure_one()
        sign_requests = self.env['sign.request'].search([('template_id', '=', self.template_id.id)], limit=1)
        if not sign_requests:
            self.attachment_id.name = name or self.attachment_id.name
            return True
        return False

    def _get_preview_values(self):
        """ prepare preview values based on current user and auto field"""
        self.ensure_one()
        values_dict = {}
        phone_item_type = self.env.ref('sign.sign_item_type_phone', raise_if_not_found=False)
        company_item_type = self.env.ref('sign.sign_item_type_company', raise_if_not_found=False)
        email_item_type = self.env.ref('sign.sign_item_type_email', raise_if_not_found=False)
        name_item_type = self.env.ref('sign.sign_item_type_name', raise_if_not_found=False)
        today = fields.Date.context_today(self)
        with file_open('sign/static/demo/signature.png', 'rb') as f:
            signature_bin = BinaryBytes(f.read())
        with file_open('sign/static/img/initial_example.png', 'rb') as f:
            initial_bin = BinaryBytes(f.read())
        for it in self.sign_item_ids:
            role_name = it.responsible_id.name
            value = None
            if it.type_id == name_item_type:
                value = self.env._("%s's name", role_name)
            elif it.type_id == phone_item_type:
                value = "+1 555-555-5555 (%s)" % role_name
            elif it.type_id == company_item_type:
                value = self.env._("%s Company", role_name)
            elif it.type_id == email_item_type:
                value = "%s@example.com" % role_name.lower()
            elif it.type_id.item_type == "signature":
                value = image_data_uri(signature_bin.content)
            elif it.type_id.item_type == "initial":
                value = image_data_uri(initial_bin.content)
            elif it.type_id.item_type == "text":
                value = self.env._("Sample generated by Odoo for %s.", role_name)
            elif it.type_id.item_type == 'date':
                value = format_date(self.env, today)
            elif it.type_id.item_type == "textarea":
                value = self.env._("""Odoo is a suite of open source business apps
that cover all your company needs:
CRM, eCommerce, accounting, inventory, point of sale,\nproject management, etc.
            """)
            elif it.type_id.item_type == "stamp":
                value = self.env._("""My US Company\n1034 Wildwood Street\n44654 Millersburg Ohio United States\n+1 555-555-5556""")
            elif it.type_id.item_type == "checkbox":
                value = "on"
            elif it.type_id.item_type == "selection":
                value = it.option_ids[:1].id  # we select always the first option
            elif it.type_id.item_type == "radio":
                radio_items = it.radio_set_id.radio_items
                value = "on" if it == radio_items[:1] else ""  # we select always the first option
            elif it.type_id.item_type == "strikethrough":
                value = "striked"
            values_dict[it.id] = {
                "value": value,
                "frame": "",
                'frame_has_hash': False,
            }
        signed_values = values_dict
        return signed_values, values_dict

    def _register_fonts(self):
        """
        Register all fonts that will be used for the PDF rendering.
        This method should be called once during initialization to ensure
        that the fonts are available in pdfmetrics.
        """
        document_fonts_str = self.env["ir.config_parameter"].sudo().get_str("sign.document.fonts")
        raw = (document_fonts_str or "").replace(';', '\n')
        fonts = [f.strip() for f in raw.splitlines() if f.strip()]
        fonts_names = []
        for idx, font in enumerate(DEFAULT_FONT_FILES + fonts):
            if not font:
                continue

            font = font.strip()
            name = f"Font_{idx}"
            try:
                pdfmetrics.registerFont(TTFont(name, font))
                fonts_names.append(name)
            except (TTFError, FileNotFoundError, OSError, ValueError):
                _logger.warning("Font file %s not found, skipping.", font)

        return fonts_names

    def _get_font_for_char(self, char, current_font=None, fonts_name=None):
        """ Return the first registered font that contains the given character.

        :param str char: The single character to find a supporting font for.
        :param str current_font: The preferred font to try first.
        :param list[str] fonts_name: List of available font names to search.
        :return: The name of the first font that contains the character,
        or "Helvetica" as a fallback if none contains it.
        """
        default_font = "Helvetica"

        fonts_name = fonts_name or []
        fonts_name = [default_font] + fonts_name
        if current_font:
            fonts_name = [current_font] + fonts_name

        for font_name in fonts_name:
            face = pdfmetrics.getFont(font_name).face

            # Basic Latin characters (0-255) are generally supported by standard fonts in WinAnsi
            # Euro Unicode code point is 8364 (0x20AC), which is also supported by Helvetica
            if font_name == default_font:
                if ord(char) < 256 or char == '€':
                    return font_name
            if (
                    (hasattr(face, "charToGlyph") and ord(char) in face.charToGlyph) or
                    (hasattr(face, "charWidths") and ord(char) in face.charWidths) or
                    (hasattr(face, "glyphNames") and char in face.glyphNames)
            ):
                return font_name

        return default_font  # fallback if none found

    def _parse_multilang_string(self, fonts_name, text):
        """ Split a string into segments based on the fonts needed to render each character.

        :param list[str] fonts_name: List of available font names.
        :param str text: The text to split into font-specific segments.
        :return: List of tuples (font_name, text_segment) representing the
        segmented string for multi-font rendering.
        """
        if not text:
            return []

        text_segments = []
        current_font = None
        buffer = ""

        for ch in text:
            font = self._get_font_for_char(ch, current_font, fonts_name)
            if font != current_font:
                if buffer:
                    text_segments.append((current_font, buffer))
                    buffer = ""
                current_font = font
            buffer += ch

        # append remaining buffer
        if buffer:
            text_segments.append((current_font, buffer))

        return text_segments

    def _draw_multilang_string(self, can, x, y, text_segments, font_size=14, alignment="center"):
        """ Draw a multilingual string on a PDF canvas with automatic font switching.

        :param Canvas can: ReportLab canvas to draw on.
        :param float x: X coordinate for the starting point.
        :param float y: Y coordinate for the baseline of the text.
        :param list[tuple[str, str]] text_segments: List of (font_name, text) segments.
        :param float font_size: Font size to use for drawing.
        :param str alignment: Horizontal alignment: "left", "center", or "right".
        """
        text_width = self._get_text_segments_width(text_segments, font_size)
        if alignment == "center":
            x -= text_width // 2

        for font_name, text in text_segments:
            text = reshape_text(text)
            can.setFont(font_name, font_size)
            if alignment == "left" or alignment == "center":
                can.drawString(x, y, text)
                x += stringWidth(text, font_name, font_size)
            else:  # alignment = right
                can.drawRightString(x, y, text)
                x -= stringWidth(text, font_name, font_size)

    def _build_multifont_paragraph(self, name, text_segments, font_size=14, leading=12):
        """ Build a ReportLab Paragraph object from a list of text segments with different fonts.

        :param str name: Name of the paragraph style.
        :param list[tuple[str, str]] text_segments: List of (font_name, text) segments.
        :param float font_size: Font size to use.
        :param float leading: Line spacing (leading) for the paragraph.
        :return: A ReportLab Paragraph object ready for drawing on a canvas.
        """
        parts = []
        for font_name, text in text_segments:
            text = reshape_text(text)
            parts.append(f'<font name="{font_name}">{text}</font>')

        full_paragraph = ''.join(parts)
        return Paragraph(full_paragraph, ParagraphStyle(name=name, fontSize=font_size, leading=leading))

    def _get_text_segments_width(self, text_segments, font_size):
        """ Compute the total width of a parsed multi-font string.

        :param list[tuple[str, str]] text_segments: List of (font_name, text) segments.
        :param float font_size: Font size to calculate width for.
        :return: Total width of the text in points.
        """
        text_width = 0
        for font_name, text in text_segments:
            text_width += stringWidth(text, font_name, font_size)

        return text_width

    def _get_drawn_text_area(self, x, y, text_segments, font_size=14, alignment="center"):
        """ Calculates the bounding box for a multi-language string.

        :param float x: X coordinate the string is drawn from.
        :param float y: Y coordinate of the baseline the string is drawn on.
        :param list[tuple[str, str]] text_segments: List of (font_name, text) segments.
        :param float font_size: Font size the string is drawn at.
        :param str alignment: Horizontal alignment: "left", "center", or "right".
        :return: The area ``(x0, y0, x1, y1)`` covered by the string, ascenders and descenders included.
        """
        text_width = self._get_text_segments_width(text_segments, font_size)
        ascent = descent = 0
        for font_name, _text in text_segments:
            font_ascent, font_descent = pdfmetrics.getAscentDescent(font_name, font_size)
            ascent = max(ascent, font_ascent)
            descent = min(descent, font_descent)

        if alignment == "center":
            x -= text_width // 2
        elif alignment == "right":
            x -= text_width

        return (x, y + descent, x + text_width, y + ascent)

    def _get_normal_font_size(self):
        return 0.015

    @api.model
    def _get_page_size(self, pdf_reader):
        max_width = max_height = 0
        for page in pdf_reader.pages:
            media_box = page.mediabox
            width = media_box and media_box.width
            height = media_box and media_box.height
            max_width = max(width, max_width)
            max_height = max(height, max_height)

        return (max_width, max_height) if max_width and max_height else None

    def _load_pdf(self):
        """Load the raw PDF bytes from the attachment.

        :return: Parsed PDF reader object.
        :rtype: PdfFileReader
        :raises ValidationError: If the PDF has no pages or corrupt.
        """
        try:
            pdf = PdfFileReader(io.BytesIO(self.attachment_id.raw), strict=False)
            len(pdf.pages)
        except (ValueError, PdfReadError):
            raise ValidationError(self.env._("ERROR: Invalid PDF file!"))

        return pdf

    def render_certificate_signature_widget(self, common_name, signing_time, logo_image=None):
        """
        Generate the visual appearance stream for the signature annotation.

        Creates a ReportLab PDF buffer showing the signing certificate's common name
        and the signing time, ready to be embedded as a Form XObject.

        :param common_name: Subject common name of the signing certificate.
        :param datetime signing_time: Timestamp of the signature action.
        :param logo_image: Optional image drawn to the left of the text (anything
            :class:`~reportlab.lib.utils.ImageReader` accepts).
        :return: In-memory PDF buffer containing the signature text, or None if unavailable.
        :rtype: io.BytesIO
        """
        self.ensure_one()

        old_pdf = self._load_pdf()
        if old_pdf.is_encrypted or not common_name or signing_time is None:
            return None

        page = old_pdf.pages[0]
        page_height = float(abs(page.mediabox.height))

        # Signature Content
        date_str = signing_time.strftime('%Y-%m-%d %H:%M:%S UTC')
        line1 = self.env._("Digitally signed by %(common_name)s", common_name=common_name)
        line2 = self.env._("Date: %s", date_str)
        safe_line1 = html_escape(line1)
        safe_line2 = html_escape(line2)
        widget_str = f"{safe_line1}<br/>{safe_line2}"

        # Font Setup
        fonts_name = self._register_fonts()
        normalFontSize = self._get_normal_font_size()
        font_size = page_height * normalFontSize * 0.65
        leading = font_size * 1.2  # 20% extra spacing

        # Calculate the width of the longest line
        line1_segments = self._parse_multilang_string(fonts_name, line1)
        line2_segments = self._parse_multilang_string(fonts_name, line2)
        line1_width = self._get_text_segments_width(line1_segments, font_size)
        line2_width = self._get_text_segments_width(line2_segments, font_size)

        max_line_width = max(line1_width, line2_width)

        # Build the Signature Paragraph
        text_segments = self._parse_multilang_string(fonts_name, widget_str)
        sig_paragraph = self._build_multifont_paragraph(
            name="SignatureStyle",
            text_segments=text_segments,
            font_size=font_size,
            leading=leading
        )

        # Wrap the Paragraph using the calculated max_line_width
        # The paragraph will claim 'max_line_width', and calculate the exact height it needs
        sig_width, sig_height = sig_paragraph.wrap(max_line_width, page_height)

        # Optional branding logo, scaled to the text height and drawn to its left
        logo_reader = ImageReader(logo_image) if logo_image is not None else None
        logo_gap = 6
        logo_width = 0
        if logo_reader is not None:
            image_width, image_height = logo_reader.getSize()
            logo_height = sig_height
            logo_width = image_width * (logo_height / image_height)

        # Define Padding and Calculate Final Canvas Dimensions
        padding = 5  # Add 5 points of space on all sides
        text_offset = padding + (logo_width + logo_gap if logo_width else 0)
        canvas_width = text_offset + sig_width + padding
        canvas_height = sig_height + (padding * 2)

        # Setup ReportLab Canvas with the calculated dimensions
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=(canvas_width, canvas_height))

        # Mostly opaque background so the appearance stays legible over existing page content.
        can.saveState()
        can.setFillColorRGB(1, 1, 1)
        can.setFillAlpha(0.9)
        can.rect(0, 0, canvas_width, canvas_height, fill=1, stroke=0)
        can.setStrokeColorRGB(0.8, 0.8, 0.8)
        can.setLineWidth(1)
        can.rect(1, 1, canvas_width - 2, canvas_height - 2, fill=0, stroke=1)
        can.restoreState()

        if logo_reader is not None:
            can.drawImage(logo_reader, padding, padding, logo_width, logo_height, mask='auto')
        sig_paragraph.drawOn(can, text_offset, padding)

        can.save()
        packet.seek(0)

        return packet

    def _render_log_hash_overlay(self, final_log_hash):
        """ Renders the final signature log hash as a reference text on every page.

        :param final_log_hash: The last hash of the request's sign log chain.
        :return: In-memory PDF buffer to merge over the document, and the area the text
            covers on each page, keyed by page index.
        :rtype: tuple[io.BytesIO, dict]
        """
        self.ensure_one()
        old_pdf = self._load_pdf()
        fonts_name = self._register_fonts()
        ref_text = f"Signature: {final_log_hash}"

        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=self._get_page_size(old_pdf))
        overlay_regions = {}
        for page_index, page in enumerate(old_pdf.pages):
            width = float(abs(page.mediabox.width))
            height = float(abs(page.mediabox.height))
            font_size = height * 0.01
            text_segments = self._parse_multilang_string(fonts_name, ref_text)
            self._draw_multilang_string(can, width / 3, height - 15, text_segments, font_size=font_size)
            overlay_regions[page_index] = [_annotation_rect(can, [
                self._get_drawn_text_area(width / 3, height - 15, text_segments, font_size=font_size)])]
            can.showPage()

        can.save()
        packet.seek(0)
        return packet, overlay_regions

    def render_document_with_items(self, signed_values=None, values_dict=None):
        self.ensure_one()
        items_by_page = self._get_sign_items_by_page()
        if not signed_values or not values_dict:
            signed_values, values_dict = self._get_preview_values()

        old_pdf = self._load_pdf()

        if old_pdf.is_encrypted:
            return

        fonts_name = self._register_fonts()
        normalFontSize = self._get_normal_font_size()

        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=self._get_page_size(old_pdf))
        overlay_regions = {}
        for p, page in enumerate(old_pdf.pages):
            # Absolute values are taken as it depends on the MediaBox template PDF metadata, they may be negative
            width = float(abs(page.mediabox.width))
            height = float(abs(page.mediabox.height))

            # Translate the canvas to match the offset of the original page,
            box = page.cropbox if page.get('/CropBox') else page.mediabox
            if box and box.lower_left:
                offset_x = float(box.lower_left[0])
                offset_y = float(box.lower_left[1])
            else:
                offset_x, offset_y = 0.0, 0.0
            can.translate(offset_x, offset_y)

            # Set page orientation (either 0, 90, 180 or 270)
            rotation = page.get('/Rotate', 0)
            if rotation and isinstance(rotation, int):
                can.rotate(rotation)
                # Translate system so that elements are placed correctly
                # despite of the orientation
                if rotation == 90:
                    width, height = height, width
                    can.translate(0, -height)
                elif rotation == 180:
                    can.translate(-width, -height)
                elif rotation == 270:
                    width, height = height, width
                    can.translate(-width, 0)

            items = items_by_page.get(p + 1, [])
            for item in items:
                value_dict = signed_values.get(item.id)
                if not value_dict:
                    continue
                # only get the 1st
                value = value_dict['value']
                frame = value_dict['frame']
                item_box = (
                    width * item.posX,
                    height * (1 - item.posY - item.height),
                    width * (item.posX + item.width),
                    height * (1 - item.posY),
                )
                drawn_areas = []  # what this item paints, the item box included as soon as it draws anything
                if frame:
                    try:
                        image_reader = ImageReader(io.BytesIO(base64.b64decode(frame[frame.find(',') + 1:])))
                    except UnidentifiedImageError:
                        raise ValidationError(self.env._("There was an issue downloading your document. Please contact an administrator."))
                    _fix_image_transparency(image_reader._image)
                    can.drawImage(
                        image_reader,
                        width * item.posX,
                        height * (1 - item.posY - item.height),
                        width * item.width,
                        height * item.height,
                        'auto',
                        True
                    )
                    drawn_areas.append(item_box)

                if item.type_id.item_type in ["text", "date"]:
                    text_segments = self._parse_multilang_string(fonts_name, value)
                    font_size = height * item.height * 0.8
                    baseline = height * (1 - item.posY - item.height * 0.9)
                    if item.alignment == "left":
                        text_x, text_alignment = width * item.posX, "left"
                    elif item.alignment == "right":
                        text_x, text_alignment = width * (item.posX + item.width), "right"
                    else:
                        text_x, text_alignment = width * (item.posX + item.width / 2), "center"
                    self._draw_multilang_string(
                        can,
                        text_x,
                        baseline,
                        text_segments,
                        font_size=font_size,
                        alignment=text_alignment
                    )
                    if text_segments:
                        drawn_areas.append(self._get_drawn_text_area(
                            text_x, baseline, text_segments, font_size=font_size, alignment=text_alignment))

                elif item.type_id.item_type == "selection":
                    text = ""
                    for option in item.option_ids:
                        if option.id == int(value):
                            text = option.value
                    font_size = height * normalFontSize * 0.8
                    text_segments = self._parse_multilang_string(fonts_name, text)
                    string_width = self._get_text_segments_width(text_segments, font_size)
                    paragraph = self._build_multifont_paragraph("Selection Paragraph", text_segments, font_size=font_size, leading=12)
                    paragraph_height = paragraph.wrap(width, height)[1]
                    posX = width * (item.posX + item.width * 0.5) - string_width // 2
                    posY = height * (1 - item.posY - item.height * 0.5) - paragraph_height // 2
                    paragraph.drawOn(can, posX, posY)
                    if text:
                        drawn_areas.append((posX, posY, posX + string_width, posY + paragraph_height))

                elif item.type_id.item_type in ["textarea", "stamp"]:
                    font_size = height * normalFontSize * 0.8
                    # Normalize line endings to handle various formats (Windows \r\n, Unix \n, Mac \r)
                    normalized_value = (value or '').replace('\r\n', '\n').replace('\r', '\n')
                    # Wrap long lines that exceed field width
                    wrapped_lines = []
                    field_width = width * item.width
                    for line in normalized_value.splitlines():
                        if not line:
                            wrapped_lines.append("")
                        else:
                            # Calculate an approximate character limit based on average width
                            avg_char_width = can.stringWidth(line, "Helvetica", font_size) / len(line)
                            max_chars = max(1, int((field_width - 4) / avg_char_width))  # -4 for padding
                            wrapped_lines.extend(textwrap.wrap(line, width=max_chars, replace_whitespace=False))
                    y = (1 - item.posY)
                    for line in wrapped_lines:
                        text_segments = self._parse_multilang_string(fonts_name, line)
                        string_width = self._get_text_segments_width(text_segments, font_size)
                        empty_space = field_width - string_width
                        x_shift = 0
                        if item.alignment == 'center':
                            x_shift = empty_space / 2
                        elif item.alignment == 'right':
                            x_shift = empty_space
                        y -= normalFontSize * 0.9
                        self._draw_multilang_string(
                            can,
                            width * item.posX + x_shift,
                            height * y,
                            text_segments,
                            font_size=font_size,
                            alignment="left"
                        )
                        drawn_areas.append(self._get_drawn_text_area(
                            width * item.posX + x_shift, height * y, text_segments, font_size=font_size, alignment="left"))
                        y -= normalFontSize * 0.1

                    # Draw a dark blue border around the stamp field for visual emphasis
                    if item.type_id.item_type == "stamp":
                        padding = 5
                        itemW, itemH = item.width * width, item.height * height
                        itemX, itemY = item.posX * width, (1 - item.posY) * height
                        border_width = 1.2
                        can.setLineWidth(border_width)  # thickness of border
                        can.setStrokeColorRGB(0, 0, 139 / 255)  # darkblue border
                        can.rect(
                            itemX - padding,
                            itemY - itemH - padding,
                            itemW + (2 * padding),
                            itemH + (2 * padding),
                            stroke=1,
                            fill=0
                        )
                        # a stroke is centered on its path, so half of it falls outside the border
                        drawn_areas.append((
                            itemX - padding - border_width / 2,
                            itemY - itemH - padding - border_width / 2,
                            itemX + itemW + padding + border_width / 2,
                            itemY + padding + border_width / 2,
                        ))

                elif item.type_id.item_type == "checkbox":
                    itemW, itemH = item.width * width, item.height * height
                    itemX, itemY = item.posX * width, (1 - item.posY) * height
                    meanSize = (itemW + itemH) // 2
                    box_width = max(meanSize // 30, 1)
                    can.setLineWidth(box_width)
                    can.rect(itemX, itemY - itemH, itemW, itemH)
                    drawn_areas.append((
                        itemX - box_width / 2,
                        itemY - itemH - box_width / 2,
                        itemX + itemW + box_width / 2,
                        itemY + box_width / 2,
                    ))
                    if value == 'on':
                        check_width = max(meanSize // 20, 1)
                        can.setLineWidth(check_width)
                        can.bezier(
                            itemX + 0.20 * itemW, itemY - 0.35 * itemH,
                            itemX + 0.30 * itemW, itemY - 0.8 * itemH,
                            itemX + 0.30 * itemW, itemY - 1.2 * itemH,
                            itemX + 0.85 * itemW, itemY - 0.15 * itemH,
                        )
                        # a bezier curve stays within the hull of its control points, the lowest of
                        # which hangs below the box
                        drawn_areas.append((
                            itemX + 0.20 * itemW - check_width / 2,
                            itemY - 1.2 * itemH - check_width / 2,
                            itemX + 0.85 * itemW + check_width / 2,
                            itemY - 0.15 * itemH + check_width / 2,
                        ))
                elif item.type_id.item_type == "radio":
                    x = width * item.posX
                    y = height * (1 - item.posY)
                    w = item.width * width
                    h = item.height * height
                    # Calculate the center of the sign item rectangle.
                    c_x = x + w * 0.5
                    c_y = y - h * 0.5
                    # Draw the outer empty circle.
                    can.circle(c_x, c_y, h * 0.5)
                    circle_width = can._lineWidth
                    drawn_areas.append((
                        c_x - h * 0.5 - circle_width / 2,
                        c_y - h * 0.5 - circle_width / 2,
                        c_x + h * 0.5 + circle_width / 2,
                        c_y + h * 0.5 + circle_width / 2,
                    ))
                    if value == "on":
                        # Draw the inner filled circle.
                        can.circle(x_cen=c_x, y_cen=c_y, r=h * 0.5 * 0.75, fill=1)
                elif item.type_id.item_type == "signature" or item.type_id.item_type == "initial":
                    try:
                        image_reader = ImageReader(io.BytesIO(base64.b64decode(value[value.find(',') + 1:])))
                    except UnidentifiedImageError:
                        raise ValidationError(self.env._("There was an issue downloading your document. Please contact an administrator."))
                    _fix_image_transparency(image_reader._image)
                    can.drawImage(image_reader, width * item.posX, height * (1 - item.posY - item.height), width * item.width, height * item.height, 'auto', True)
                    drawn_areas.append(item_box)
                elif item.type_id.item_type == "strikethrough" and value == "striked":
                    x = width * item.posX
                    y = height * (1 - item.posY)
                    w = item.width * width
                    h = item.height * height
                    can.line(x, y - 0.5 * h, x + w, y - 0.5 * h)
                    line_width = can._lineWidth
                    drawn_areas.append((
                        x,
                        y - 0.5 * h - line_width / 2,
                        x + w,
                        y - 0.5 * h + line_width / 2
                    ))

                if drawn_areas:
                    # the value is shown through an annotation of its own, so it can neither be
                    # covered by, nor cover, the value of another sign item
                    overlay_regions.setdefault(p, []).append(_annotation_rect(can, drawn_areas + [item_box]))
            can.showPage()

        can.save()
        packet.seek(0)

        return packet, overlay_regions

    def _copy_sign_items_to(self, new_document):
        """ Copy all sign items of the self document to the new_document that fit within its page count."""
        self.ensure_one()
        if new_document.template_id.has_sign_requests:
            raise UserError(self.env._("Somebody is already filling a document which uses this template"))

        new_document_pages = new_document.num_pages
        item_id_map = {}
        for sign_item in self.sign_item_ids:
            # Only copy sign items that fit within the new document's page range.
            if sign_item.page <= new_document_pages:
                new_sign_item = sign_item.copy({'document_id': new_document.id})
                new_sign_item.responsible_id = sign_item.responsible_id.id
                item_id_map[str(sign_item.id)] = str(new_sign_item.id)
        return item_id_map

    @api.model
    def _check_pdf_data_validity(self, pdf_data):
        try:
            self._get_pdf_number_of_pages(pdf_data)
        except ValueError as e:
            raise UserError(self.env._("One uploaded file cannot be read. Is it a valid PDF?")) from e

    @api.model
    def _get_pdf_number_of_pages(self, pdf_data):
        file_pdf = get_valid_pdf_data(pdf_data, strict=False)
        return len(file_pdf.pages)
