# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from markupsafe import Markup

# Matches AI citation tokens such as [SOURCE:210] or [SOURCE:210, 211]
CITATION_REGEX = re.compile(r"""
    \[SOURCE:
        (\s*[0-9]+
            (?:\s*,\s*[0-9]+)*
        )
    \]
""", re.VERBOSE)

WEB_CITATION_REGEX = re.compile(r"""
    \(?\t*
        \[WEB_SOURCE:
            ([a-f0-9]+
                (?:\s*,\s*[a-f0-9]+)*
            )
        \]
    \t*\)?
""", re.VERBOSE)


def get_sources_ids_from_text(text):
    """
    Return unique sources ids from inline AI citation tags in the provided text.
    """
    if not text:
        return []
    sources = CITATION_REGEX.findall(text)
    sources_ids = [int(id.strip()) for source in sources for id in source.split(',')]
    return list(set(sources_ids))


def apply_numeric_citations(text, source_data, link_attrs='target="_blank" rel="noreferrer noopener"'):
    """
    Replace inline citations with numbered, clickable citations [1][2]...
    :param text: The input text containing citation placeholders (e.g., [SOURCE:ID1, ID2, ...])
    :param source_data: Map of source_id -> {'url', 'source_name'}
    :param link_attrs: HTML attributes for the citation link
    :return: new_content if source_data, text otherwise
    :rtype: str
    """
    if not text:
        return ""

    if not source_data:
        return text

    new_content = ""
    text_pieces = CITATION_REGEX.split(text)
    resolved_citations = {}
    for index, text_piece in enumerate(text_pieces):
        if index % 2 == 0:
            new_content += text_piece.rstrip(" ")
        else:
            source_ids = text_piece.split(',')
            for source_id in source_ids:
                source_id_int = int(source_id.strip())
                source_info = source_data.get(source_id_int, {})
                if not source_info:
                    continue
                if source_id_int not in resolved_citations:
                    citation_num = len(resolved_citations) + 1
                    resolved_citations[source_id_int] = citation_num
                else:
                    citation_num = resolved_citations[source_id_int]
                new_content += Markup("<sup>%s</sup>") % (
                    source_info._get_source_link(f"[{citation_num}]")
                )

    return new_content


def apply_web_citations(text, sources, link_attrs='target="_blank" rel="noreferrer noopener"'):
    if not text:
        return ""
    new_content = ""
    text_pieces = WEB_CITATION_REGEX.split(text)
    for index, text_piece in enumerate(text_pieces):
        if index % 2 == 0:
            # content (text) before the citation
            # stripped because there's sometimes a whitespace between the dot and the source.
            new_content += text_piece.rstrip()
        else:
            # uuid's of the sources
            for idx in text_piece.split(','):
                source = sources.get(idx.strip())
                if not source:
                    continue
                href = source['url']
                source_name = source['source_name']
                # only strip ".com" if it's a simple domain (no subdomain)
                if len(parts := source_name.split(".")) == 2 and parts[-1] == "com":
                    source_name = parts[0]
                citation_html = f' <a href="{href}" {link_attrs} class="btn btn-sm btn-outline-secondary rounded-pill fw-light py-0">{source_name}</a>'
                # json.loads may be called on the returned data and json.loads throws an error if values have double quotes.
                new_content += citation_html.replace('"', "'")
    return new_content
