# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging
import os
import requests
import urllib

from odoo.exceptions import UserError
from odoo.tools import split_every


_logger = logging.getLogger(__name__)


def meta_run_request_batch(env, queries):
    """Execute many requests in batch.

    Return a list of JSON response in the same order (or None for the requests that failed).

    In the `social` module, and not in `social_facebook`, so `social_instagram`
    doesn't need to depend on `social_facebook`.

    :param env: Odoo environment
    :param queries: List of dict representing the requests
        The keys supported for the requests are:
        - method
        - url
        - params
        - files: {'name': ('name', b'data', 'mimetype')}
    """
    if not queries:
        return []

    # At least one access token should be set in the root as fallback
    # (see https://developers.facebook.com/docs/graph-api/batch-requests)
    access_token = next((
        token for query in queries
        if (token := (query.get('params') or {}).get("access_token"))
    ), None)
    if not access_token:
        raise UserError(env._("At least one access token should be set."))

    result = []
    for queries_batch in split_every(50, queries):
        # Meta can batch up to 50 queries
        meta_batch_requests = []
        batched_files = {}
        for query in queries_batch:
            method = query.get('method', 'GET')
            url = query['url']
            params = query.get('params')
            files = query.get('files')
            if params:
                url += f"?{urllib.parse.urlencode(params)}"

            meta_request = {
                "method": method,
                "relative_url": url,
            }

            if files:
                # Generate one identifier for each file,
                # and add the identifier in `attached_files`
                files_identifiers = []
                for filename, raw, mimetype in files.values():
                    file_identifier = os.urandom(8).hex()
                    files_identifiers.append(file_identifier)
                    batched_files[file_identifier] = (filename, raw, mimetype)
                meta_request['attached_files'] = ','.join(files_identifiers)

            meta_batch_requests.append(meta_request)

        response = requests.post(
            env['social.media']._FACEBOOK_ENDPOINT_VERSIONED,
            params={
                "batch": json.dumps(meta_batch_requests),
                "access_token": access_token,
            },
            files=batched_files or None,
            timeout=40 if batched_files or len(queries_batch) > 10 else 20,
        )

        if not response.ok:
            _logger.error("Meta: Failed to make requests for %s", queries_batch[0]['url'])
            result.extend([None] * len(queries_batch))
            continue

        for meta_r, query in zip(response.json(), queries_batch):
            status_code = meta_r.get("code")
            response_ok = status_code and (status_code // 100 == 2)
            response_content = meta_r.get("body", "")
            try:
                response_content = json.loads(response_content)
            except json.JSONDecodeError:
                response_ok = False

            if not response_ok:
                _logger.error("Meta: Failed to make requests for %s, %s", query['url'], response_content)
                response_content = None

            result.append(response_content)

    return result
