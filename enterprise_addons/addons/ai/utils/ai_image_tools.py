import base64
import math
import mimetypes
import requests
from typing import Any
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import HTTPException
from urllib.parse import urlsplit
from logging import getLogger

from odoo.api import Environment
from odoo.exceptions import MissingError, UserError
from odoo.http.router import root
from odoo.tools.mimetypes import MIMETYPE_HEAD_SIZE, guess_mimetype
from odoo.tools import file_open
from odoo.tools.image import ImageProcess

from .types import AIMessageParts

_logger = getLogger(__name__)

AI_SUPPORTED_IMG_TYPES = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

# formats are the same as content_image method in Binary controller
IMAGE_PATH_FORMATS = [
    '/web/image',
    '/web/image/<string:xmlid>',
    '/web/image/<string:xmlid>/<string:filename>',
    '/web/image/<string:xmlid>/<int:width>x<int:height>',
    '/web/image/<string:xmlid>/<int:width>x<int:height>/<string:filename>',
    '/web/image/<string:model>/<int:id>/<string:field>',
    '/web/image/<string:model>/<int:id>/<string:field>/<string:filename>',
    '/web/image/<string:model>/<int:id>/<string:field>/<int:width>x<int:height>',
    '/web/image/<string:model>/<int:id>/<string:field>/<int:width>x<int:height>/<string:filename>',
    '/web/image/<int:id>',
    '/web/image/<int:id>/<string:filename>',
    '/web/image/<int:id>/<int:width>x<int:height>',
    '/web/image/<int:id>/<int:width>x<int:height>/<string:filename>',
    '/web/image/<int:id>-<string:unique>',
    '/web/image/<int:id>-<string:unique>/<string:filename>',
    '/web/image/<int:id>-<string:unique>/<int:width>x<int:height>',
    '/web/image/<int:id>-<string:unique>/<int:width>x<int:height>/<string:filename>'
]

"""
All the methods are adapted from `ir.binary` and `ir.attachment`.
"""


def _is_ai_supported_mimetype(mimetype):
    extension = (mimetype or '').split('/')[-1]
    return extension in AI_SUPPORTED_IMG_TYPES


def _unsupported_image_text_part(image_path, mimetype):
    return {
        'type': 'text',
        'text': (
            f"The existing image at '{image_path}' is in a format ({mimetype}) that cannot be read or "
            "edited. If the request requires viewing or modifying this exact image, ask the user to "
            "provide it as a JPEG, PNG, GIF or WEBP file, or to describe it in enough detail to recreate "
            "it from scratch. Ignore this note if the request is to generate a brand-new image instead."
        ),
    }


def retrieve_image_parts_from_path(env: Environment, image_path: str) -> AIMessageParts:
    if not image_path:
        return []

    image_path = urlsplit(image_path).path
    if root.get_static_file(image_path, host=env.context.get('HTTP_HOST', '')):
        return _retrieve_image_parts_from_file(image_path)

    args = _retrieve_record_args_from_path(image_path)
    if not args:
        return []
    try:
        record = env['ir.binary']._find_record(
            xmlid=args.get('xmlid'),
            res_model=args['model'],
            res_id=args['id'],
            field=args['field']
        )
    except MissingError:
        return []
    return _retrieve_image_parts_from_record(record, args.get('field'), image_path)


def _retrieve_image_parts_from_file(image_file_path: str) -> AIMessageParts:
    try:
        # The path starts with a forward slash (/), it should be stripped out.
        file_path = image_file_path[1:]
        with file_open(file_path, 'rb') as file:
            content = file.read()
            mimetype = mimetypes.guess_type(file_path)[0]
            if not _is_ai_supported_mimetype(mimetype):
                return [_unsupported_image_text_part(image_file_path, mimetype)]
            return [{
                'type': 'inline_data',
                'mimetype': f'{mimetypes.guess_type(file_path)[0]}',
                'data': base64.b64encode(content).decode(),
                'metadata': {
                    'image_path': image_file_path,
                    'aspect_ratio': _get_aspect_ratio_from_raw(content)
                }
            }]
    except FileNotFoundError:
        return []


def _retrieve_record_args_from_path(image_path: str) -> dict[str, Any]:
    """
    We are only interested in extracting model, id, field and xml_id as these are used
    to retrieve the base64 encoded image. Other attributes like width, height, filename
    are not relevant for the AI.
    """
    path_map = Map([Rule(path_format, endpoint='dummy') for path_format in IMAGE_PATH_FORMATS])
    # Host is irrelevant here because there is no host-based url matching. bind() just needs a dummy value
    adapter = path_map.bind('localhost')
    try:
        __, args = adapter.match(image_path)
    except HTTPException:
        return {}
    args['model'] = args.get('model', 'ir.attachment')
    args['id'] = args.get('id') and int(args.get('id'))
    args['field'] = args.get('field', 'raw')
    return args


def _retrieve_image_parts_from_record(record, field_name: str, image_path=None) -> AIMessageParts:
    image_data = retrieve_image_data_from_record(record, field_name)
    if not image_data['content']:
        return []
    if not _is_ai_supported_mimetype(image_data['mimetype']):
        return [_unsupported_image_text_part(image_path, image_data['mimetype'])]
    return [{
        'type': 'inline_data',
        'mimetype': image_data['mimetype'],
        'data': base64.b64encode(image_data['content']).decode(),
        'metadata': {
            'image_path': image_path if image_path else field_to_image_path(record, field_name),
            'aspect_ratio': _get_aspect_ratio_from_raw(image_data['content'])
        }
    }]


def retrieve_image_data_from_record(record, field_name: str) -> dict:
    """
    :param record: the record of the image field.
    :param field_name: the binary field of the image
    :rtype: a dict with keys:
        'content' => the raw content of the image (could be empty if the image couldn't be retrieved),
        'mimetype' => the mimetype of the image. Defaults to "image/png" if no mimetype could be retrieved/guessed unless
        content is empty, in which case the mimetype is 'application/x-empty'
    """
    image_src = _retrieve_image_src_and_mimetype_from_record(record, field_name)

    content = b''
    mimetype = image_src['mimetype']
    if data := image_src.get('data'):
        content = data
    elif path := image_src.get('path'):
        with file_open(path, 'rb') as file:
            content = file.read()
    elif url := image_src.get('url'):
        # The URL of the image is an external URL (no data is saved in Odoo file store).
        response = requests.request("GET", url, timeout=10)
        try:
            # Make sure the returned response is actually an image.
            ImageProcess(response.content)
            content = response.content
        except UserError:
            content = b''

    if record._name == 'ir.attachment':
        mimetype = record.mimetype
    # 'application/octet-stream' is the default mimetype for attachments if the no mimetype is found.
    # See _compute_mimetype in ir.attachment. However, it is not supported by LLMs, so we default to image/png.
    if mimetype == 'application/octet-stream' or mimetype == 'application/x-empty':
        mimetype = guess_mimetype(content[:MIMETYPE_HEAD_SIZE], default='image/png')
    return {
        'content': content,
        'mimetype': mimetype if content else 'application/x-empty'
    }


def _retrieve_image_src_and_mimetype_from_record(record, field_name: str) -> dict:
    """
    :param record: the record of the image field.
    :param str field_name: the binary field of the image
    :rtype: a dict having one of
        'data' => the raw image content
        or 'path' => the static addons path of the image, for example ai/static/description/icon.png
        or 'url' => The url from which the image content should be retrieved
    """

    field = record._fields.get(field_name)
    if field is None:
        return {'data': b'', 'mimetype': 'application/x-empty'}

    if field.type != 'binary':
        raise ValueError(f"Field {field_name} is not a binary field")
    record.check_field_access(field, 'read')

    if record._name == 'ir.attachment' and field_name in ('raw', 'db_datas'):
        return record._retrieve_image_src_and_mimetype()

    data = record[field_name].content or b''
    return {'data': data, 'mimetype': record[field_name].mimetype if data else 'application/x-empty'}


def closest_aspect_ratio(*, width=None, height=None, aspect_ratio=None):
    if width and height:
        aspect_ratio = _calculate_aspect_ratio(width, height)

    supported_aspect_ratios = [
        '21:9', '16:9', '9:16',
        '5:4', '4:5', '4:3', '3:4',
        '3:2', '2:3', '1:1'
    ]
    result = min(
        supported_aspect_ratios,
        key=lambda x: abs(int(x.split(':')[0]) / int(x.split(':')[1]) - int(aspect_ratio.split(':')[0]) / int(aspect_ratio.split(':')[1]))
    )
    return result


def _calculate_aspect_ratio(width, height):
    if not width or not height:
        return '1:1'

    w = round(width)
    h = round(height)
    divisor = math.gcd(w, h)
    return f'{w // divisor}:{h // divisor}'


def _get_aspect_ratio_from_raw(raw):
    aspect_ratio = '1:1'
    size = None
    try:
        image_process = ImageProcess(raw)
        size = image_process.image.size
    except Exception as e:  # noqa: BLE001
        _logger.error("The raw data doesn't represent an image %s", e)
    finally:
        if size:
            aspect_ratio = closest_aspect_ratio(width=size[0], height=size[1])
    return closest_aspect_ratio(aspect_ratio=aspect_ratio)


def field_to_image_path(record, field_name: str) -> str:
    return f'/web/image/{record._name}/{record.id}/{field_name}'
