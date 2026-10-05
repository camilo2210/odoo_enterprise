# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import logging

from odoo.tools.urls import urljoin

_logger = logging.getLogger(__name__)


def get_urbanpiper_image_url(urbanpiper_store, record):
    """
    Get public image URL for the given record (product or category).
    Converts webp to jpeg if necessary.
    """
    base_url = urbanpiper_store.get_base_url()
    image_data = record.image_1920 if record._name == 'product.template' else record.image_128
    if not image_data:
        return False
    attachment = record.env['ir.attachment'].search([
        ('res_model', '=', record._name),
        ('res_id', '=', record.id),
        ('type', '=', 'binary'),
        ('public', '=', True),
        ('mimetype', '=', 'image/jpg'),
    ], limit=1)
    raw = get_jpeg_bytes(urbanpiper_store, image_data)
    if attachment:
        attachment.raw = raw
    else:
        attachment = record.env['ir.attachment'].create({
            'name': record.name,
            'type': 'binary',
            'raw': raw,
            'res_model': record._name,
            'res_id': record.id,
            'public': True,
            'mimetype': 'image/jpg',
        })
    local_url = attachment.local_url
    return urljoin(base_url, local_url)


def get_jpeg_bytes(urbanpiper_store, raw):
    """Get the image data in jpeg format."""
    try:
        data_uri = urbanpiper_store.env['ir.qweb'].with_context(webp_as_jpg=True)._get_converted_image_data_uri(raw)
        _header, base64_data = data_uri.split('base64,', 1)
        return base64.b64decode(base64_data)
    except TypeError as err:
        _logger.info('UrbanPiper: JPEG image conversion failed (%s)', err)
        return raw
