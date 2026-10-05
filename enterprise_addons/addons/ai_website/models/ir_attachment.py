# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ipaddress
import logging
import re
from time import monotonic
from urllib.parse import unquote, urlsplit

import requests
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool

from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools.image import image_process
from odoo.tools.mimetypes import guess_mimetype

from odoo.addons.html_editor.controllers.main import attachment_create
from odoo.addons.html_editor.models.ir_attachment import SUPPORTED_IMAGE_MIMETYPES

_logger = logging.getLogger(__name__)

ALLOWED_IMAGE_SCHEMES = ('http', 'https')
_IMAGE_DOWNLOAD_TIMEOUT = 8
_IMAGE_DOWNLOAD_BATCH_DEADLINE = 25
_MAX_IMAGE_BYTES = 20 * 1024 * 1024
_MAX_IMAGE_REDIRECTS = 3
_MAX_IMAGES_PER_BATCH = 30


class _PublicConnectionPoolMixin:

    def _validate_conn(self, conn):
        """Check the connected peer before sending any HTTP request, including on reuse.

        Checking a separate DNS lookup would both repeat resolution and leave a gap
        where the address could change before urllib3 establishes its connection.
        """
        super()._validate_conn(conn)
        # HTTPS validation already connects; HTTP normally connects when sending.
        if conn.sock is None:
            conn.connect()
        # urllib3's PyOpenSSL wrapper exposes the underlying socket as `socket`.
        try:
            sock = conn.sock.socket
        except AttributeError:
            sock = conn.sock
        ip = ipaddress.ip_address(sock.getpeername()[0])
        if isinstance(ip, ipaddress.IPv6Address):
            ip = ip.ipv4_mapped or ip
        if not ip.is_global or ip.is_multicast or ip.is_reserved:
            raise ValueError("only publicly reachable hosts are allowed.")


class _PublicHTTPConnectionPool(_PublicConnectionPoolMixin, HTTPConnectionPool):
    pass


class _PublicHTTPSConnectionPool(_PublicConnectionPoolMixin, HTTPSConnectionPool):
    pass


def _read_image_response(response):
    content_length = response.headers.get('content-length')
    if content_length and content_length.isdigit() and int(content_length) > _MAX_IMAGE_BYTES:
        raise ValueError(f"image is larger than {_MAX_IMAGE_BYTES // (1024 * 1024)}MB.")
    content = bytearray()
    for chunk in response.iter_content(chunk_size=64 * 1024):
        content += chunk
        if len(content) > _MAX_IMAGE_BYTES:
            raise ValueError(f"image is larger than {_MAX_IMAGE_BYTES // (1024 * 1024)}MB.")
    return bytes(content)


class _ImageHTTPAdapter(requests.adapters.HTTPAdapter):

    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = {
            'http': _PublicHTTPConnectionPool,
            'https': _PublicHTTPSConnectionPool,
        }

    def build_response(self, req, resp):
        response = super().build_response(req, resp)
        if response.is_redirect:
            # Requests consumes the body to prepare Response.next, even with
            # stream=True. Bound that read and release the connection for reuse.
            with response:
                response._content = _read_image_response(response)
        return response


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model
    def _download_external_image(self, url, session):
        """Download an external image and return its validated ``(bytes, mimetype)``.

        The batch's session uses a public-address-only adapter for every redirect.
        The body is read in chunks and capped so a URL cannot stream an unbounded
        response into memory.

        :raises ValueError: with a message meant for the caller, if the image can't be used.
        """
        parsed_url = urlsplit(url)
        if parsed_url.scheme not in ALLOWED_IMAGE_SCHEMES or not parsed_url.hostname:
            raise ValueError("only HTTP(S) image URLs are supported.")
        try:
            request = session.prepare_request(requests.Request('GET', url))
        except requests.RequestException as err:
            raise ValueError("image could not be reached.") from err
        for _redirect in range(_MAX_IMAGE_REDIRECTS + 1):
            try:
                response = session.send(
                    request,
                    timeout=_IMAGE_DOWNLOAD_TIMEOUT,
                    stream=True,
                    allow_redirects=False,
                )
                with response:
                    if response.next is not None:
                        request = response.next
                        continue
                    if response.status_code != 200:
                        raise ValueError(f"the server answered with HTTP {response.status_code}.")
                    content = _read_image_response(response)
            except requests.RequestException as err:
                raise ValueError("image could not be reached.") from err
            if not content:
                raise ValueError("the URL returned an empty response.")
            try:
                image_data = image_process(content, verify_resolution=True)
            except (UserError, OSError, ValueError) as err:
                raise ValueError("URL does not point to a supported image.") from err
            mimetype = guess_mimetype(image_data)
            if mimetype not in SUPPORTED_IMAGE_MIMETYPES:
                raise ValueError("URL does not point to a supported image.")
            return image_data, mimetype
        raise ValueError("too many redirects.")

    @api.model
    def _get_image_name_from_url(self, url, mimetype):
        """Build an attachment name from the URL's last path segment.

        The extension is forced to match ``mimetype``: `_compute_mimetype` trusts the name
        over the content, so a wrong extension would leave the attachment with a mimetype
        that does not describe its bytes (and no usable ``image_src``).
        """
        extension = SUPPORTED_IMAGE_MIMETYPES[mimetype]
        basename = unquote(urlsplit(url).path).rpartition('/')[2].strip()
        # Keep it a plain file name: no separators, no leading dots, bounded length.
        basename = re.sub(r'[^\w.\- ]', '', basename).lstrip('.').strip()
        basename = basename.rpartition('.')[0][:100].strip() or basename[:100].strip()
        return f"{basename or 'External image'}{extension}"

    @api.model
    def _create_attachment_from_external_image_url(self, url, session):
        """Download one external image URL and return the local attachment holding it.

        :raises ValueError: with a message meant for the caller, if the image can't be used.
        """
        image_data, mimetype = self._download_external_image(url, session)
        # No `url=` here on purpose: passing one makes `image_src` point back at the
        # external URL, which would defeat the download.
        try:
            attachment = attachment_create(
                self.env['ir.attachment'],
                name=self._get_image_name_from_url(url, mimetype),
                data=image_data,
            )
        except UserError as err:
            # Size limit, access rights, ... AccessError is a UserError.
            raise ValueError(str(err)) from err
        if not attachment.image_src:
            _logger.warning(
                "Attachment %s created from %s has no image_src (mimetype %s)",
                attachment.id, url, attachment.mimetype,
            )
            raise ValueError("the image could not be stored.")
        return attachment

    @api.model
    def _localize_external_image_urls(self, urls):
        """Copy external images into Odoo and map each source URL to a local one.

        A URL that cannot be localized is reported rather than raised: the caller keeps a
        working - if hotlinked - page instead of a failed save.

        :param urls: external image URLs to download.
        :return: ``{'sources': {url: local_url}, 'errors': {url: message}}``
        """
        sources = {}
        errors = {}
        deduplicated_urls = list(dict.fromkeys(
            url.strip()
            for url in (urls or [])
            if isinstance(url, str) and url.strip()
        ))[:_MAX_IMAGES_PER_BATCH]

        # Downloads run one after the other, so they share a deadline. Past it the
        # remaining URLs are reported as failures without being attempted: a save that
        # keeps a few hotlinks beats a save that hangs on a slow host.
        deadline = monotonic() + _IMAGE_DOWNLOAD_BATCH_DEADLINE
        with requests.Session() as session:
            # A proxy would hide the target peer's address. Also avoid sending netrc
            # credentials when fetching URLs supplied by third-party pages.
            session.trust_env = False
            for scheme in ALLOWED_IMAGE_SCHEMES:
                session.mount(f'{scheme}://', _ImageHTTPAdapter())
            for url in deduplicated_urls:
                if monotonic() > deadline:
                    errors[url] = "the images took too long to download."
                    continue
                try:
                    sources[url] = self._create_attachment_from_external_image_url(url, session).image_src
                except ValueError as err:
                    # Everything that makes a URL unusable is rejected before any attachment
                    # is created, so a rejected URL leaves nothing behind to clean up.
                    errors[url] = str(err)

        if errors:
            _logger.info("Could not localize %s external image(s): %s", len(errors), errors)
        return {'sources': sources, 'errors': errors}
