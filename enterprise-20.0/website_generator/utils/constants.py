from odoo.tools import LazyTranslate

_lt = LazyTranslate(__name__)

DEFAULT_WSS_ENDPOINT = 'https://iap-scraper.odoo.com/'
STATUS_MESSAGES = {
    'success': _lt("Success"),
    'processing': _lt("Processing"),
    'waiting': _lt("Waiting for the server to process the request"),
    'draft': _lt("Draft, record created but request not yet accepted by the server"),
    'done': _lt("Done, website generated"),
    'error_maintenance': _lt("Server is currently under maintenance. Please retry later"),
    'error_internal': _lt("An error occurred"),
    'error_invalid_url': _lt("Invalid url"),
    'error_banned_url': _lt("Banned url"),
    'error_invalid_dbuuid': _lt("Invalid dbuuid"),
    'error_too_many_pages': _lt("The request asks for too many pages"),
    'error_unsupported_version': _lt("Version is unsupported"),
    'error_invalid_token': _lt("Invalid token"),
    'error_concurrent_request': _lt("Number of concurrent requests exceeded"),
    'error_allowed_request_exhausted': _lt("Number of allowed requests exhausted"),
    'error_invalid_import_products': _lt("Invalid import products"),
    'error_invalid_request_uuid': _lt("Could not fetch result, invalid output uuid or result expired"),
    'error_request_still_processing': _lt("Request is still processing, result not available yet"),
    'error_attachment_not_found': _lt("Attachment not found"),
    'errror_website_not_supported': _lt("Website not supported"),
    'error_website_blocked': _lt("Website blocked or unreachable"),
    'error_navigation_timeout': _lt("The requested url took too long to load and is probably unreachable from the server"),
    'error_url_redirection': _lt("The requested url redirected to another url, try again with the redirected url"),
    'error_duplicated_request': _lt("The same request has just been made, please wait before sending another identical request"),
}
