# Part of Odoo. See LICENSE file for full copyright and licensing details.

import contextlib
import logging
import re

import psycopg2
from lxml import etree as lxml_etree
from lxml import html as lxml_html
from markupsafe import Markup

from odoo import api, models
from odoo.exceptions import ConcurrencyError
from odoo.tools.image import image_process

from odoo.addons.base.models.assetsbundle import AssetsBundle, StylesheetAsset
from odoo.addons.html_editor.controllers.main import attachment_create
from odoo.addons.web.icons import search_icons

_logger = logging.getLogger(__name__)

# A DB error leaves the transaction unusable, so a failure path must not fail open on one.
_UNRECOVERABLE = (psycopg2.Error, ConcurrencyError)

_USER_CUSTOM_RULES_URL = '/website/static/src/scss/user_custom_rules.scss'
_USER_CUSTOM_RULES_BUNDLE = 'web.assets_frontend'

_MAX_ACTIONS = 50
_MAX_ACTION_CONTENT_LENGTH = 500_000
_MAX_CSS_CONTENT_LENGTH = 100_000

# Also stated in the per-message context, see `_get_context_input` on `ai.session`.
MAX_GENERATED_IMAGES = 10

_WHOLE_ZONE_SELECTORS = {
    'main': frozenset({'main', 'body', 'html', 'div#wrap', '#wrap'}),
    'footer': frozenset({'footer', '#footer', 'footer#bottom', 'footer#bottom > #footer'}),
}

_ANIMATION_RUNTIME_CLASSES = frozenset({
    'o_visible', 'o_animated', 'o_animating', 'o_animate_preview', 'o_animate_in_dropdown',
})
_ANIMATION_RUNTIME_STYLE_PROPS = ('visibility', 'animation-play-state', 'animation-name')

_PALETTE_TEXT_CLASSES = frozenset({'text-light', 'text-dark'})

_ICON_SHAPE_CLASSES = frozenset({'rounded', 'rounded-circle', 'rounded-0', 'rounded-leaf', 'img-thumbnail', 'shadow'})
_PADDING_UTILITY_RE = re.compile(
    r'^p[tbsexy]?(-(sm|md|lg|xl|xxl))?-\d+$'  # bootstrap: p-3, pt-3, px-lg-3
    r'|^p[tbxy]?\d+$'                          # odoo: p16, pt48, pb16
)

# JavaScript patterns that allow data exfiltration or cross-frame attacks.
# The AI safety reviewer runs first, but this regex catches the most critical
# patterns deterministically.
_DANGEROUS_JS_RE = re.compile(
    r'eval\s*\('
    r'|new\s+Function\s*\('
    r'|document\.cookie'
    r'|navigator\.sendBeacon'
    r'|(?<!\w)WebSocket\s*\(|(?<!\w)EventSource\s*\('
    r'|window\.top|window\.parent|window\.opener'
    r'|\.contentDocument|\.contentWindow'
    r'|(?<!\w)postMessage\s*\('
    r'|(?<!\w)import\s*\(|(?<!\w)require\s*\('
    r'|set(?:Timeout|Interval)\s*\(\s*[\'\"]'
    r'|document\.write(?:ln)?\s*\('
    r'|createElement\s*\(\s*[\'\"`]\s*(?:script|iframe|object|embed)'
    r'|\.\s*srcdoc\b'
    r'|setHTMLUnsafe\s*\('
    r'|javascript\s*:',
    re.IGNORECASE,
)

_SCRIPT_TAG_RE = re.compile(r'<\s*script[\s>]', re.IGNORECASE)

# CSS patterns that can be used for script injection or data exfiltration.
_DANGEROUS_CSS_RE = re.compile(
    r'javascript\s*:'              # javascript: URLs inside url()
    r'|@import\s+(?:url\()?["\']?https?://',  # External stylesheet imports
    re.IGNORECASE,
)


class AIWebsiteService(models.AbstractModel):
    _name = 'ai.website.service'
    _description = "AI Website Service"

    @api.model
    def _current_website(self):
        """The website being edited. `self.env.website` is only populated from a
        `website_id` context key, so the id the builder sends comes first."""
        website_id = (
            self.env.context.get('current_view_info', {})
            .get('website_page', {})
            .get('website_id')
        )
        if website_id:
            return self.env['website'].browse(website_id)
        return self.env.website or self.env.ref('base.default_website')

    @api.model
    def _parse_html_fragment(self, html):
        """Parse an HTML fragment under a synthetic <div> wrapper; raises
        ParserError/ValueError on bad input."""
        return lxml_html.fragment_fromstring(html, create_parent='div')

    @api.model
    def _serialize_html_fragment(self, element):
        """Inner HTML of a parsed element (its own tag dropped); inverse of
        ``_parse_html_fragment``."""
        return (element.text or '') + ''.join(
            lxml_html.tostring(child, encoding='unicode') for child in element)

    @api.model
    def _create_public_image_url(self, attachment):
        """
        Create a permanent attachment for the given attachment and return its
        public URL.
        Note: ensure the attachment is supposed to be public before calling
        this method.
        """
        attachment.ensure_one()
        image = image_process(attachment.raw.content, verify_resolution=True)
        attachment_data = {
            'name': attachment.name,
            'data': image,
        }
        new_attachment = attachment_create(self.env['ir.attachment'], **attachment_data)
        return new_attachment.image_src

    @api.model
    def _ai_scripts_allowed(self, session_state):
        """Whether the AI may add JavaScript, website-wide or just in this chat."""
        return bool(
            self._current_website().ai_allow_scripts
            or session_state.get('website_ai_allow_scripts')
        )

    @api.model
    def _strip_animation_runtime_state(self, content):
        """Strip the Animation interaction's runtime classes + inline
        visibility/animation props from AI HTML; saved, they freeze or hide
        animated elements on the public site."""
        if not content or ('o_animat' not in content and 'o_visible' not in content):
            return content
        try:
            fragment = self._parse_html_fragment(content)
        except (lxml_etree.ParserError, ValueError):
            return content
        for el in fragment.iter():
            classes = el.get('class') or ''
            if not classes:
                continue
            if _ANIMATION_RUNTIME_CLASSES & set(classes.split()):
                el.set('class', ' '.join(c for c in classes.split() if c not in _ANIMATION_RUNTIME_CLASSES))
            style = el.get('style')
            if style and 'o_animate' in classes:
                kept = [d.strip() for d in style.split(';')
                        if d.strip() and d.split(':', 1)[0].strip().lower() not in _ANIMATION_RUNTIME_STYLE_PROPS]
                if kept:
                    el.set('style', '; '.join(kept) + ';')
                else:
                    el.attrib.pop('style')
        return self._serialize_html_fragment(fragment)

    @api.model
    def _strip_palette_text_utilities(self, content):
        """Drop `text-light`/`text-dark`: they are palette slots 3 and 5, not shades, so on a dark palette the text vanishes into its background.
           Often happens as LLM is told to generate bootstrap, so conflict on that class happen"""
        if not content or not any(cls in content for cls in _PALETTE_TEXT_CLASSES):
            return content
        try:
            fragment = self._parse_html_fragment(content)
        except (lxml_etree.ParserError, ValueError):
            return content
        for el in fragment.iter():
            classes = (el.get('class') or '').split()
            if not _PALETTE_TEXT_CLASSES.intersection(classes):
                continue
            kept = [c for c in classes if c not in _PALETTE_TEXT_CLASSES]
            if kept:
                el.set('class', ' '.join(kept))
            else:
                el.attrib.pop('class')
        return self._serialize_html_fragment(fragment)

    @api.model
    def _find_icon_by_keywords(self, keywords):
        """Return the name of the first icon whose name or tags match one of the
        given keywords, trying keywords in order."""
        for keyword in keywords:
            if not keyword.strip():
                continue
            if match := next(search_icons(keyword), None):
                return match[0]
        return None

    @api.model
    def _generate_placeholder_icons(self, content):
        """
        Fill in every `data-ai-icon-keywords` placeholder the AI left behind.
        This is done by letting the AI choose 3 keywords and looking for matches
        for an icon. Once found, we replace in text the correct icon.
        """
        if not content or 'data-ai-icon-keywords' not in content:
            return content
        try:
            fragment = self._parse_html_fragment(content)
        except (lxml_etree.ParserError, ValueError):
            return content
        placeholders = fragment.xpath('.//*[@data-ai-icon-keywords]')
        if not placeholders:
            return content
        for element in placeholders:
            keywords = element.attrib.pop('data-ai-icon-keywords').split(',')
            if icon_name := self._find_icon_by_keywords(keywords):
                element.set('data-icon', icon_name)
        return self._serialize_html_fragment(fragment)

    @api.model
    def _fix_icon_shape_padding(self, content):
        """
        The AI keeps adding extra padding on the icons so this class removes
        them if found.
        """
        if not content or 'oi' not in content:
            return content
        try:
            fragment = self._parse_html_fragment(content)
        except (lxml_etree.ParserError, ValueError):
            return content
        changed = False
        for el in fragment.iter():
            classes = (el.get('class') or '').split()
            if 'oi' not in classes or not _ICON_SHAPE_CLASSES.intersection(classes):
                continue
            kept = [c for c in classes if not _PADDING_UTILITY_RE.match(c)]
            if len(kept) != len(classes):
                el.set('class', ' '.join(kept))
                changed = True
        return self._serialize_html_fragment(fragment) if changed else content

    @api.model
    def _validate_html_actions(self, actions, session_state):
        """Sanity-check the HTML actions produced by the AI, raising on anything
        unsafe or out of bounds. The markup is sanitized in the builder, which
        knows to set the AI scripts aside first."""
        if len(actions) > _MAX_ACTIONS:
            raise ValueError(f"Too many actions {len(actions)}. Maximum allowed per call is {_MAX_ACTIONS}.")

        for i, action in enumerate(actions):
            content = action.get('content', '')
            content_length = len(content)
            if content_length > _MAX_ACTION_CONTENT_LENGTH:
                raise ValueError(f"Action #{i}: content is too long ({content_length} characters). Maximum allowed is {_MAX_ACTION_CONTENT_LENGTH} characters.")

            # The JavaScript gates run on the raw content, before any rewriting.
            if _SCRIPT_TAG_RE.search(content) and not self._ai_scripts_allowed(session_state):
                raise ValueError(
                    f"Action #{i}: adding JavaScript is turned off. Ask the user whether "
                    "to allow it this time, always, or not at all, and do not "
                    "try to deliver this behaviour some other way."
                )

            if _DANGEROUS_JS_RE.search(content):
                raise ValueError(f"Action #{i}: content contains a forbidden pattern.")

    @api.model
    def _find_image_placeholders(self, content):
        try:
            fragment = self._parse_html_fragment(content)
        except (lxml_etree.ParserError, ValueError):
            return None, []
        return fragment, fragment.xpath('.//*[@data-ai-image-prompt]')

    @api.model
    def _validate_image_placeholders(self, actions):
        """
        To avoid dropping images later in _generate_placeholder_images which could
        create ugly content, we instead try to catch the mistakes now and make the agent
        retry.
        """
        image_count = 0
        blank_prompt_action_indexes = []
        for i, action in enumerate(actions):
            content = action.get('content')
            if not content:
                continue
            _fragment, placeholders = self._find_image_placeholders(content)
            image_count += len(placeholders)
            if not all((p.get('data-ai-image-prompt') or '').strip() for p in placeholders):
                blank_prompt_action_indexes.append(str(i))

        # Accumulate the errors and raise them in one go.
        errors = []
        if image_count > MAX_GENERATED_IMAGES:
            errors.append(
                f"{image_count} images requested across all actions, but at most {MAX_GENERATED_IMAGES} "
                "can be generated per call. Reduce the number of `data-ai-image-prompt` placeholders, "
                "or split the actions across multiple calls, and try again.",
            )
        if blank_prompt_action_indexes:
            actions_label = "Action" if len(blank_prompt_action_indexes) == 1 else "Actions"
            errors.append(
                f"{actions_label} {', '.join(blank_prompt_action_indexes)}: has a "
                "`data-ai-image-prompt` placeholder with a blank prompt. Fill in a prompt for every "
                "image placeholder, or remove the placeholder, and try again.",
            )
        if errors:
            raise ValueError(" ".join(errors))

    @api.model
    def _sanitize_html_actions(self, actions):
        """Normalise HTML actions produced by the AI in place: clear the selector
        on a whole-zone replace and rewrite content the model shouldn't hand-author
        (animation runtime state, palette text utilities, icon padding/keywords)."""
        for action in actions:
            selector = (action.get('selector') or '').strip()
            whole_zone_selectors = _WHOLE_ZONE_SELECTORS.get(action.get('zone'), frozenset())
            if action.get('mode') == 'replace' and selector.lower() in whole_zone_selectors:
                action['selector'] = ''
            content = action.get('content', '')
            content = self._strip_animation_runtime_state(content)
            content = self._strip_palette_text_utilities(content)
            content = self._fix_icon_shape_padding(content)
            action['content'] = self._generate_placeholder_icons(content)

    @api.model
    def _get_website_assets(self):
        return self.env['website.assets'].with_context(website_id=self._current_website().id)

    @api.model
    def _read_custom_css(self):
        """Read the current content of user_custom_rules.scss."""
        assets = self._get_website_assets()
        content = assets._get_content_from_url(
            assets._make_custom_asset_url(
                _USER_CUSTOM_RULES_URL, _USER_CUSTOM_RULES_BUNDLE), {'customized': True}
        ).decode()
        if content and content.strip():
            return content.strip()
        return "The user_custom_rules.scss file is empty (no custom CSS rules yet)."

    @api.model
    def _validate_css_content(self, css_content):
        """
        Guard against known CSS injection patterns and enforce a size limit.
        """
        content_length = len(css_content)
        if content_length > _MAX_CSS_CONTENT_LENGTH:
            raise ValueError(f"CSS content is too large ({content_length} characters). Maximum allowed is {_MAX_CSS_CONTENT_LENGTH} characters.")

        if _DANGEROUS_CSS_RE.search(css_content):
            raise ValueError("CSS content contains potentially dangerous patterns (e.g javascript:, external @import).")

    @api.model
    def _compile_custom_css(self, css_content):
        """Compile AI provided SCSS against the frontend bundle without saving it."""
        if not css_content or not css_content.strip():
            return
        fake_bundle = 'ai_website.custom_css_validation'
        # Inline content skips StylesheetAsset._fetch_content, which rewrites
        # relative url()s with the asset's /_custom/... path. That can break
        # valid SCSS (e.g. `url($var)`), so we test it here.
        custom_url = self._get_website_assets()._make_custom_asset_url(_USER_CUSTOM_RULES_URL, _USER_CUSTOM_RULES_BUNDLE)
        web_dir = custom_url.rsplit('/', 1)[0]
        css_content = StylesheetAsset.rx_url.sub(fr"url(\1{web_dir}/", css_content)

        bundle = AssetsBundle(
            fake_bundle,
            [{
                'url': 'custom_ai_css.scss',
                'filename': '',
                'content': css_content,
                'last_modified': None,
                'definition_bundle': fake_bundle
            }],
            {},
            env=self.env,
            css=True,
            js=False,
            assets_params={},
        )
        bundle.preprocess_css()
        if bundle.css_errors:
            raise ValueError("\n".join(bundle.css_errors))

    @api.model
    def _save_custom_css(self, css_content):
        """Validate, compile, persist user_custom_rules.scss and reload the
        bundles. Shared by the write-css tool and the refinement CSS pass so
        neither can skip a validation step."""
        scoped = self.with_context(website_id=self._current_website().id)
        scoped._validate_css_content(css_content)
        scoped._compile_custom_css(css_content)
        scoped.env['website.assets'].save_asset(
            _USER_CUSTOM_RULES_URL, _USER_CUSTOM_RULES_BUNDLE,
            css_content, 'scss',
        )
        self.env.user._bus_send("ai_website/reload_css_bundles", {})

    @api.model
    def _find_unscoped_css_selectors(self, css_content):
        """Find selectors that would leak across the whole site.

        user_custom_rules.scss is loaded on every page, so a top-level rule like
        ``section {}`` restyles every section everywhere, not just the page the
        AI built. Return the bare element selectors (``section``, ``h2``, …) that
        aren't anchored to a class, id, ``&`` or ``:root``; at-rules, variables
        and placeholders (``@``/``$``/``%``) are left alone. This is a best-effort
        text scan meant to drive a warning, not a strict CSS parser."""
        content = re.sub(r'//[^\n]*', '', re.sub(r'/\*.*?\*/', '', css_content, flags=re.S))
        unscoped, depth, buf = [], 0, []
        for char in content:
            if char == '{':
                if depth == 0:
                    selector = ''.join(buf).strip().rsplit(';', 1)[-1].strip()
                    if selector and not selector.startswith(('@', '$', '%')):
                        unscoped += [p.strip() for p in selector.split(',')
                                     if p.strip() and not re.search(r'[.#&]|:root', p)]
                    buf = []
                depth += 1
            elif char == '}':
                depth = max(depth - 1, 0)
                if depth == 0:
                    buf = []
            elif depth == 0:
                buf.append(char)
        return unscoped

    @api.model
    def _format_website_menu_tree(self, website):
        """Render the website menu hierarchy as an indented text list."""
        def format_menu(menu, level):
            flags = ''
            if menu.new_window:
                flags += ', opens in a new window'
            if menu.is_mega_menu:
                flags += ', mega menu (its content cannot be edited with the available tools)'
            line = (
                f'{"    " * level}- ID: {menu.id}, Name: "{menu.name}", '
                f'URL: "{menu.url}", Sequence: {menu.sequence}{flags}\n'
            )
            return line + ''.join(format_menu(child, level + 1) for child in menu.child_id)

        top_menus = website.menu_id.child_id
        if not top_menus:
            return "The website menu is currently empty.\n"
        return ''.join(format_menu(menu, 0) for menu in top_menus)

    @api.model
    def _format_website_menu_tree_html(self, website, created_ids, updated_ids, deleted_records):
        """
        Render the (dry-run) website menu hierarchy as an HTML tree, highlighting
        additions, changes and removals for the user confirmation preview.
        """
        style_by_status = {
            'created': 'color:#1f7a1f;',
            'updated': 'color:#8a6d00;',
            'deleted': 'color:#b02a2a; text-decoration: line-through;',
        }
        label_by_status = {
            'created': self.env._(" (added)"),
            'updated': self.env._(" (changed)"),
            'deleted': self.env._(" (removed)"),
        }

        def render_node(name, new_window, is_mega_menu, status):
            flags = ''
            if new_window:
                flags += self.env._(", opens in a new window")
            if is_mega_menu:
                flags += self.env._(", mega menu")
            return Markup('<span style="%s">%s%s%s</span>') % (
                style_by_status.get(status, ''), name, flags, label_by_status.get(status, ''),
            )

        deleted_by_parent_id = {}
        for record in deleted_records:
            deleted_by_parent_id.setdefault(record['parent_id'], []).append(record)

        def render_deleted_subitems(parent_id):
            # Menus are at most two levels deep, so a deleted item's own deleted
            # sub-items (from the cascade) never have children of their own.
            records = sorted(deleted_by_parent_id.get(parent_id, []), key=lambda r: (r['sequence'], r['id']))
            if not records:
                return Markup()
            items = Markup().join(
                Markup('<li>%s</li>') % render_node(record['name'], record['new_window'], record['is_mega_menu'], 'deleted')
                for record in records
            )
            return Markup('<ul>%s</ul>') % items

        def render_children(parent_menu, parent_id):
            combined = [
                (menu.sequence, menu.id, False, menu)
                for menu in parent_menu.child_id
            ] + [
                (record['sequence'], record['id'], True, record)
                for record in deleted_by_parent_id.get(parent_id, [])
            ]
            # Maintain the order -> compare ids for menu items that share
            # the same sequence value (i.e. deleted menu and it's replacement)
            combined.sort(key=lambda entry: (entry[0], entry[1]))

            items = Markup()
            for _sequence, menu_id, is_deleted, data in combined:
                if is_deleted:
                    items += Markup('<li>%s%s</li>') % (
                        render_node(data['name'], data['new_window'], data['is_mega_menu'], 'deleted'),
                        render_deleted_subitems(menu_id),
                    )
                    continue
                status = 'created' if menu_id in created_ids else 'updated' if menu_id in updated_ids else None
                items += Markup('<li>%s%s</li>') % (
                    render_node(data.name, data.new_window, data.is_mega_menu, status),
                    render_children(data, menu_id),
                )
            return Markup('<ul>%s</ul>') % items if items else Markup()

        tree_html = render_children(website.menu_id, website.menu_id.id)
        if not tree_html:
            return Markup('<p>%s</p>') % self.env._("The website menu would be empty.")
        return tree_html

    @api.model
    def _prefetch_menus_for_operations(self, website, operations):
        """Batch-fetch every menu referenced by menu_id/parent_menu_id across the operations,
        instead of searching once per lookup."""
        referenced_ids = set()
        for operation in operations:
            for mid in (operation.get('menu_id'), operation.get('parent_menu_id')):
                if not mid:
                    continue
                with contextlib.suppress(TypeError, ValueError):
                    referenced_ids.add(int(mid))
        if not referenced_ids:
            return {}
        return {
            menu.id: menu
            for menu in self.env['website.menu'].search([
                ('id', 'in', list(referenced_ids)),
                ('website_id', '=', website.id),
            ])
        }

    @staticmethod
    def _drop_unfilled_placeholder(image):
        """Remove an <img> placeholder that got no image: kept, it renders as a broken one.
        A background element is left as-is instead: removing it would break the section's layout."""
        if image.tag == 'img' and not image.get('src') and (parent := image.getparent()) is not None:
            parent.remove(image)

    @staticmethod
    def _set_background_image(element, url):
        # Preserve the element's styles but replace the background image.
        declarations = [
            declaration for declaration in (element.get('style') or '').split(';')
            if declaration.strip() and declaration.split(':', 1)[0].strip() != 'background-image'
        ]
        declarations.append(f" background-image: url('{url}')")
        element.set('style', ';'.join(declarations).strip() + ';')

    @api.model
    def _generate_image_url(self, prompt, aspect_ratio):
        """The public URL of one generated image, or None; a failure costs its own placeholder only."""
        try:
            _result, attachments = self.env['ai.tool']._generate_image_attachments(
                prompt, [], prompt[:40], aspect_ratio)
            if attachments:
                return self._create_public_image_url(attachments[0])
        except _UNRECOVERABLE:
            raise
        except Exception:
            _logger.exception("could not generate image for %r; dropping it", prompt[:80])
        return None

    @api.model
    def _generate_placeholder_images(self, page_html, batch_size=None):
        """Fill in every `data-ai-image-prompt` placeholder the builder left behind:
        an `<img>` gets its `src` set, any other element (e.g. an `oe_img_bg` span or
        div used as a parallax/cover background) gets its `background-image` style set."""
        fragment, placeholders = self._find_image_placeholders(page_html)
        if not placeholders:
            return page_html
        if len(placeholders) > MAX_GENERATED_IMAGES:
            _logger.info("page asked for %d images, generating the first %d",
                         len(placeholders), MAX_GENERATED_IMAGES)
            for skipped in placeholders[MAX_GENERATED_IMAGES:]:
                skipped.attrib.pop('data-ai-image-prompt', None)
                self._drop_unfilled_placeholder(skipped)
            placeholders = placeholders[:MAX_GENERATED_IMAGES]

        if batch_size is not None:
            placeholders = placeholders[:batch_size]

        jobs, targets = [], []
        for image in placeholders:
            prompt = (image.get('data-ai-image-prompt') or '').strip()
            # A full-bleed background is cropped to a wide band.
            full_bleed = {'s_parallax_bg', 'oe_img_bg'} & set((image.get('class') or '').split())
            aspect_ratio = image.get('data-ai-image-aspect') or ('16:9' if full_bleed else '3:2')
            image.attrib.pop('data-ai-image-prompt')
            image.attrib.pop('data-ai-image-aspect', None)
            if prompt:
                jobs.append((prompt, aspect_ratio))
                targets.append(image)
            else:
                self._drop_unfilled_placeholder(image)

        agent = self.env.ref('ai_website.ai_agent_website_builder', raise_if_not_found=False)
        if not agent:
            _logger.warning("builder agent not found; dropping the placeholders")
            for image in targets:
                self._drop_unfilled_placeholder(image)
            return self._serialize_html_fragment(fragment)
        for image, (prompt, aspect_ratio) in zip(targets, jobs):
            if url := self._generate_image_url(prompt, aspect_ratio):
                if image.tag == 'img':
                    image.set('src', url)
                else:
                    self._set_background_image(image, url)
            else:
                self._drop_unfilled_placeholder(image)
        return self._serialize_html_fragment(fragment)
