# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
import logging
import re
from urllib.parse import quote

import psycopg2
from lxml import etree as lxml_etree
from lxml import html as lxml_html

from odoo import api, models
from odoo.exceptions import ConcurrencyError, UserError

from odoo.addons.ai.utils.ai_utils import get_text_from_parts

_logger = logging.getLogger(__name__)

# A DB error leaves the transaction unusable, so the passes below must not fail open on one.
_UNRECOVERABLE = (psycopg2.Error, ConcurrencyError)

# Kept under --limit-time-real (120s)
_REFINEMENT_PASS_TIMEOUT = 90

# Max kept length of a text node / asset URL when abridging the page for a pass.
_SKELETON_MAX_TEXT = 80
_SKELETON_MAX_URL = 160

# Below this RGB distance a bridged band is invisible ("blank divider"), so drop it.
_MIN_DIVIDER_BG_CONTRAST = 48

# `clearance` = min px padding to add on the anchored edge so content clears the shape's band.
_SHAPE_REGISTRY = {
    'Connections/01': {'position': 'bottom', 'slots': (5,), 'clearance': 96},
    'Connections/02': {'position': 'bottom', 'slots': (5,), 'clearance': 96},
    'Connections/05': {'position': 'bottom', 'slots': (5,), 'clearance': 96},
    'Connections/06': {'position': 'bottom', 'slots': (5,), 'clearance': 96},
    'Connections/07': {'position': 'bottom', 'slots': (5,), 'clearance': 96},
    'Connections/08': {'position': 'bottom', 'slots': (5,), 'clearance': 96},
    'Connections/11': {'position': 'bottom', 'slots': (5,), 'clearance': 96},
    'Connections/12': {'position': 'bottom', 'slots': (5,), 'clearance': 96},
    'Connections/15': {'position': 'bottom', 'slots': (5,), 'clearance': 96},
    'Connections/16': {'position': 'bottom', 'slots': (5,), 'clearance': 96},
    'Connections/17': {'position': 'bottom', 'slots': (5,), 'clearance': 96},
    'Connections/18': {'position': 'bottom', 'slots': (5,), 'clearance': 96},
    'Floats/01': {'position': 'center right', 'slots': (1, 2, 3, 4, 5)},
    'Floats/02': {'position': 'center', 'slots': (1, 2, 3, 5)},
    'Floats/05': {'position': 'center', 'slots': (1, 2, 3, 5)},
    'Floats/09': {'position': 'center right', 'slots': (1, 2, 3)},
    'Floats/13': {'position': 'center', 'slots': (1, 2, 5)},
    'Floats/14': {'position': 'center', 'slots': (1, 2, 3, 5)},
    'Rainy/01_001': {'position': 'bottom', 'slots': (1, 5)},
    'Rainy/02_001': {'position': 'top', 'slots': (1, 4, 5), 'clearance': 96},
    'Rainy/08_001': {'position': 'top', 'slots': (1, 4), 'clearance': 96},
    'Rainy/10': {'position': 'center', 'slots': (1, 3)},
    'Zigs/01_001': {'position': 'bottom', 'slots': (2,)},
    'Blobs/01_001': {'position': 'top', 'slots': (2,), 'clearance': 160},
    'Blobs/03': {'position': 'top', 'slots': (2,), 'clearance': 96},
    'Blobs/05_001': {'position': 'bottom', 'slots': (1,), 'clearance': 128},
    'Blobs/06_001': {'position': 'top', 'slots': (1,), 'clearance': 160},
    'Blobs/13': {'position': 'bottom', 'slots': (1, 5)},
    'Blurry/01': {'position': 'center', 'slots': (1,)},
    'Blurry/03': {'position': 'bottom', 'slots': (1, 2, 3, 4)},
    'Blurry/05': {'position': 'center', 'slots': (1, 2, 4)},
    'Blurry/06': {'position': 'center', 'slots': (1, 4)},
    'Grids/01': {'position': 'bottom', 'slots': (5,)},
    'Angular/05': {'position': 'bottom', 'slots': (5,), 'clearance': 240},
    'Angular/06': {'position': 'bottom', 'slots': (1, 3, 5), 'clearance': 240},
}

_SHAPES_PASS_SCHEMA = {
    "type": "object",
    "properties": {
        "placements": {
            "type": "array",
            "description": "Shape placements — usually several (connect most section transitions, accent the sparse sections)",
            "items": {
                "type": "object",
                "properties": {
                    "section_index": {"type": "integer",
                                      "description": "1-based index of the target section among the top-level sections"},
                    "shape": {"type": "string", "description": "Catalog key, e.g. 'Connections/02' or 'Floats/01'"},
                    "colors": {"type": "object", "description": "Color slot overrides; only slots this shape uses",
                               "properties": {slot: {"type": "string", "description": "One of o-color-1..o-color-5"}
                                              for slot in ('c1', 'c2', 'c3', 'c4', 'c5')}},
                    "edge": {"type": "string", "enum": ["top", "bottom"],
                             "description": "Which edge the divider anchors to; the system flips/repositions automatically."},
                    "flip": {"type": "string", "enum": ["x", "y", "xy"],
                             "description": "Optional aesthetic mirroring ('x'); vertical anchoring is handled by `edge`."},
                    "reason": {"type": "string", "description": "One line: why this shape serves this section"},
                },
                "required": ["section_index", "shape", "reason"],
            },
        },
    },
    "required": ["placements"],
}

_SHAPES_CATALOG = """
### How to choose — by SECTION SIZE first, then mood
- A BIG section (a hero, a CTA, a tall quote — sparse, with room to breathe and
  generous pt/pb padding) earns an ANIMATED shape: Floats, Rainy or Zigs.
- A SMALL or tight transition where two flat colour sections meet gets a thin
  static Connections divider — quiet, never animated.
- COHERENCE: pick ONE animated family for the big moments and use Connections
  for every small transition; that pairing IS the page's whole shape language.
  Never scatter two or three different animated families across one page.
- Mood only tints WHICH options you reach for within that rule: Angular ridges
  for bold/architectural, Blobs for organic/human/craft, Grids for tech/data,
  Blurry glows for premium/dreamy. The SIZE rule comes first.

### Small-transition dividers — thin band where two flat sections meet
Connections (all c5, thin band; paint them in the NEXT section's background):
01 diagonal ramp - 02 single sweeping wave - 05 dome - 06 U valley -
07 soft hill - 08 double-shoulder dip - 11 round shoulder sweep -
12 concave slope - 15 two-tone overlapping waves - 16 layered triple wave -
17 small centred peak - 18 small soft dome.

### Animated accents — BIG / sparse sections only (heroes, CTAs, big quotes)
Floats: 01 corner circle + dot grids - 02 scattered mini-shapes - 05 squiggle +
dotted circle - 09 curved S-lines right - 13 sparse confetti - 14 confetti
triangles. Rainy: 01_001 (c1,c5) flying capsule cluster - 10 (c1,c3) tiny ticks
band - 02_001 (c1,c4,c5, top) capsule streaks - 08_001 (c1,c4, top) soft streaks.
Zigs/01_001 (c2) zigzag mountain band. Blobs/01_001 (c2, TALL, top) breathing blob.

### Mood backdrops & ridges — bigger sections, static, by mood
Blurry (soft glows behind sparse hero/CTA text): 01 (c1) glowing ellipse chain -
03 (c1,c2,c3,c4) two-tone curve - 05 (c1,c2,c4) corner glows - 06 (c1,c4) right glow.
Grids/01 (c5) perspective wireframe floor (tech/data). Blobs/13 (c1,c5) two-tone
S-flow statement. Angular ridges (bold, TALL bottom dividers): 05 (c5) jagged
ridge - 06 (c1,c3,c5) layered ridge. Blobs edge dividers: 05_001 (c1, bottom)
organic mound - 03 (c2, top) quarter blob - 06_001 (c1, TALL, top) hanging blob.
"""

_SHAPES_PASS_INSTRUCTIONS = f"""
You are the decorative-shapes refinement pass of the Odoo website builder. You
receive the page's `# Mood`, the resolved palette, a `# Page map` digesting each
top-level section (its background hex with the matching `o-color-N` slot,
density, padding, photo backgrounds) and the page's HTML structure. The layout,
content, colors and animations are FINAL — your job is to make the page feel
like ONE smooth, flowing design by connecting its sections with background
shapes. A page with no shapes feels abrupt and unfinished. Base every
colour/sizing decision on the page map.

Lean toward placing shapes: aim for a divider at the MAJORITY of flat-colour
section transitions, plus an atmospheric accent on each big / sparse section.
YOUR FIRST DECISION, per section, is its SIZE (see "How to choose"): a BIG /
sparse section earns an ANIMATED shape; a SMALL / tight transition gets a thin
static Connections divider. Mood only tints which family you reach for.

# Principles
- Be generous but purposeful: most section transitions deserve a divider and
  most sparse hero/CTA sections deserve an accent. Skip a shape only when it
  would genuinely hurt (the guards below) — never as a default.
- Decide placements as ONE coherent set: one animated family for the big
  sections + Connections for the small transitions. Don't mix animated families.
- One shape per boundary: each gap hosts ONE divider (upper section's bottom OR
  lower section's top, never both).
- NEVER place a shape on a section with a photographic background — the photo is
  the interest; the shape becomes noise. Shapes belong on FLAT colour sections.
- Colors: a slot you don't specify defaults to the palette color of the same
  number. Specify a slot only for a divider painted in the neighbour's bg.
- Divider colour is a LOOKUP, not a choice: a bottom-edge divider reads as the
  NEXT section rising in — its main slot MUST be that section's background slot;
  a top-edge divider uses the PREVIOUS section's. If the facing background
  matches no slot, pick a different boundary.
- Use `edge` to anchor (top/bottom); the system flips/repositions. Don't use
  `flip` for anchoring.
- TALL shapes paint a deep band and the system raises the section's padding to
  clear them, so reserve TALL for sections with room (heroes, CTAs); on tight
  transitions use the thin Connections band.
- Backdrops (Blurry, Grids, Blobs/13) go ONLY on SPARSE sections and must stay
  low-contrast against that section's background.
- Animation belongs on BIG sections ONLY; on a small/dense section or a tight
  transition it buries the text — use a thin Connections divider there instead.

# Output
JSON placements. Each: `section_index` (1-based), `shape` (catalog key),
`colors` (only slots that shape uses, values o-color-1..o-color-5), optional
`flip`, one-line `reason`. At most ONE placement per section.

# Shape catalog (the ONLY valid keys; color slots in parentheses)
{_SHAPES_CATALOG}
"""

_CSS_PASS_SCHEMA = {
    "type": "object",
    "properties": {
        "scss": {"type": "string",
                 "description": "The COMPLETE new content of user_custom_rules.scss (existing rules preserved + additions)"},
    },
    "required": ["scss"],
}

_CSS_PASS_INSTRUCTIONS = """
You are the CSS-polish refinement pass of the Odoo website builder. You receive
the structure of a freshly generated page plus the current content of the
website-wide `user_custom_rules.scss` file. The page's layout, type, spacing and
palette are already set — your job is the finishing layer that utility classes
can't express: the tasteful touches that make it feel hand-crafted and alive.
Long text and image URLs are abridged in the HTML you receive; scope your rules
on the classes and structure, which are complete.

# Be creative — native CSS only
You are NOT working from a checklist. Polish THIS page like a front-end designer
on a final hand-off: reach for whatever genuinely elevates its character and
palette — hover / focus feedback, smooth transitions, pseudo-element accents and
dividers, gradient / overlay / blend-mode flourishes, soft tinted shadows, image
treatments (duotone, masks, `clip-path`), subtle decorative motion. Vary your
choices from page to page; surprise me with details that suit the design.

Reliable starting points (inspiration, not a mandate):
- Hover lift on cards / clickable blocks: a small `translateY` + a deeper,
  palette-tinted shadow on hover.
- Hover zoom on an image inside a clipped container (`scale(~1.04)`).
- An underline or marker that grows under inline links or a key phrase.
- One restrained signature moment mid-page — a colour-block highlight, a tinted
  image overlay, an accent behind a stat. (Gradient-clipped text is over-used and
  often looks off — use it only if it truly fits, never as a default.)
- A slow ambient background drift on a mid-page CTA (never the hero — see guardrails).
A few well-placed touches beat a page stuffed with effects.

# Guardrails (don't cross these — they keep the page from breaking)
- NATIVE CSS ONLY: no JavaScript, no external `@import` or web fonts.
- Leave the FIRST section (the hero) free of added motion: NO zoom/`scale`,
  ambient drift, parallax or any keyframe/looping animation on it or its
  background. It already carries the page's strongest imagery and Odoo's own
  entrance animations, and extra motion there fights them and looks broken.
  Static polish (shadows, overlays, gradients, accents) and hover feedback on its
  buttons are fine — continuous motion is not.
- Don't restyle what's already designed. Leave the existing layout, spacing,
  fonts and the core colours / legibility of the text and sections as they are —
  you ADD decoration (hover states, accents, overlays, shadows, flourishes); you
  don't move, resize or recolour the content the user already approved.
- Animate only cheap, non-reflowing properties (`transform`, `opacity`,
  `box-shadow`, `filter`, `background-position`, `color`). Never animate
  `width`, `height`, `margin`, `padding` or `top`/`left` — they cause layout jank.
- Scope EVERY rule under a class that exists in the provided HTML (the page's
  `ai_*` section classes, or snippet classes nested under them). This file is
  global to the whole site — no bare top-level element selectors.
- Use `var(--o-color-1)`..`var(--o-color-5)` for palette colours so it re-themes.
- Keep this token block at the top of the file (add it if missing):
  `:root { --ai-ease: cubic-bezier(0.22, 1, 0.36, 1); --ai-dur-fast: 0.25s; --ai-dur: 0.6s; }`
- Group this page's rules under a `/* === page: <page path> === */` marker,
  replacing any previous block with the same marker, and PRESERVE every other
  page's rules — return the COMPLETE new file content. Valid SCSS only.

# Output
JSON: {"scss": "<complete new file content>"}
"""


def _parse_css_color(value):
    """'#RGB', '#RRGGBB' or 'rgb(a)(r, g, b)' -> (r, g, b), else None."""
    value = (value or '').strip()
    if m := re.fullmatch(r'#([0-9A-Fa-f]{6})', value):
        return tuple(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))
    if m := re.fullmatch(r'#([0-9A-Fa-f]{3})', value):
        return tuple(int(c * 2, 16) for c in m.group(1))
    if m := re.fullmatch(r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)[^)]*\)', value):
        return tuple(int(m.group(i)) for i in (1, 2, 3))
    return None


def _bump_edge_padding(section, edge, min_px):
    """Raise the section's pt/pb utility class to at least min_px (never shrink)
    so content clears the shape band on `edge`."""
    prefix = 'pt' if edge == 'top' else 'pb'
    classes = (section.get('class') or '').split()
    current = next((c for c in classes if re.fullmatch(rf'{prefix}\d+', c)), None)
    if current and int(current[2:]) >= min_px:
        return
    if current:
        classes[classes.index(current)] = f'{prefix}{min_px}'
    else:
        classes.append(f'{prefix}{min_px}')
    section.set('class', ' '.join(classes))


class AIWebsiteService(models.AbstractModel):
    _inherit = 'ai.website.service'

    @api.model
    def _finalize_page(self, page_html, step='images'):
        """Generate the page's images and run the refinement passes; every step fails open.

        Runs in separate requests (`/ai_website/finalize_page`), called by the
        `finalize_website_page` client tool: the server kills a worker at
        `--limit-time-real` (120s by default), and generation alone already costs
        ~45s, so the build is split across the tool-pause request, one request per
        image batch, one for both refinement passes, and the resumed turn.
        """
        # `env.website` comes from the request host, not the site being edited.
        service = self.with_context(website_id=self._current_website().id)
        page_html = service._unwrap_sections_container(page_html)
        if step == 'images':
            page_html = service._generate_placeholder_images(page_html, batch_size=4)
            _fragment, remaining_placeholders = service._find_image_placeholders(page_html)
            next_step = 'images' if remaining_placeholders else 'refinements'
            return {'html': page_html, 'next_step': next_step}

        has_failed_pass = False
        try:
            live_palette = service._live_palette_css_variables()
            if live_palette:
                view_info = dict(service.env.context.get('current_view_info') or {})
                website_page = dict(view_info.get('website_page') or {})
                # The bundle wins: it is the CSS the page and the shape controller both resolve against.
                website_page['css_variables'] = {**(website_page.get('css_variables') or {}), **live_palette}
                view_info['website_page'] = website_page
                service = service.with_context(current_view_info=view_info)
            shape_actions, _shape_count = service._refinement_shapes_pass(page_html)
            if shape_actions:
                page_html = service._apply_section_replacements(page_html, shape_actions)
        except _UNRECOVERABLE:
            raise
        except Exception:
            has_failed_pass = True
            _logger.exception("shapes refinement failed; continuing with CSS")

        try:
            service._refinement_css_pass(page_html)
        except _UNRECOVERABLE:
            raise
        except Exception:
            has_failed_pass = True
            _logger.exception("CSS refinement failed; returning the partially refined page")
        return {'html': page_html, 'next_step': None, 'error': has_failed_pass}

    @api.model
    def _live_palette_css_variables(self):
        """Palette ({'o-color-N' | 'o-ccN-bg': '#hex'}) read from the compiled web.assets_frontend bundle, or {}."""
        website_id = self._current_website().id
        if not website_id:
            return {}
        try:
            bundle = self.env['ir.qweb'].with_context(website_id=website_id)._get_asset_bundle('web.assets_frontend')
            # NOT bundle.css(): recompiling races the browser doing the same and aborts the
            # transaction. Reading is enough, the builder reloads the bundle before calling us.
            attachment = (bundle.get_attachments('min.css') or bundle.get_attachments('css'))[:1]
            css = attachment.index_content if attachment else ''
        except _UNRECOVERABLE:
            raise
        except Exception:
            _logger.exception("could not read live palette from the frontend bundle")
            return {}
        if not css:
            return {}
        color = r'#[0-9A-Fa-f]{6,8}|rgba?\([^)]*\)'
        wanted = [f'o-color-{n}' for n in range(1, 6)] + [f'o-cc{n}-bg' for n in range(1, 6)]
        palette = {}
        for name in wanted:
            if match := re.search(r'(?i)--%s:\s*(%s)' % (re.escape(name), color), css):
                palette[name] = match.group(1).strip()
        return palette

    @api.model
    def _unwrap_sections_container(self, page_html):
        """Return the inner HTML when the page's sections are wrapped in a single
        container element, so section detection sees them at top level (mirrors
        the JS apply pipeline's unwrap). Unchanged otherwise."""
        try:
            fragment = self._parse_html_fragment(page_html)
        except (lxml_etree.ParserError, ValueError):
            return page_html
        children = [el for el in fragment if isinstance(el.tag, str)]
        if len(children) == 1:
            inner = children[0]
            if sum(1 for c in inner if isinstance(c.tag, str) and c.tag == 'section') > 1:
                return self._serialize_html_fragment(inner)
        return page_html

    @api.model
    def _html_structure_skeleton(self, page_html):
        """The page HTML with long text nodes and asset URLs abridged. The passes
        decide from structure and headings, so body copy and image URLs are most
        of the tokens and none of the signal. Unchanged if it can't be parsed."""
        def abridge(text):
            if not text:
                return text
            collapsed = re.sub(r'\s+', ' ', text)
            if len(collapsed.strip()) <= _SKELETON_MAX_TEXT:
                return text
            return collapsed[:_SKELETON_MAX_TEXT].rstrip() + '…'

        try:
            fragment = self._parse_html_fragment(page_html)
        except (lxml_etree.ParserError, ValueError):
            return page_html
        for el in fragment.iter():
            if not isinstance(el.tag, str):
                continue
            el.text = abridge(el.text)
            el.tail = abridge(el.tail)
            for attribute in ('src', 'href', 'data-original-src'):
                value = el.get(attribute)
                if value and len(value) > _SKELETON_MAX_URL:
                    el.set(attribute, value[:_SKELETON_MAX_URL] + '…')
        return self._serialize_html_fragment(fragment)

    @api.model
    def _apply_section_replacements(self, page_html, actions):
        """Apply a pass's section:nth-child(N) replace actions onto page_html and
        return the merged HTML, so a later pass building on it sees the earlier
        edits. Falls back to the unchanged HTML on any parse error."""
        replacements = {}
        for action in actions:
            match = re.fullmatch(r'section:nth-child\((\d+)\)', (action.get('selector') or '').strip())
            if match and action.get('mode') == 'replace' and action.get('content'):
                replacements[int(match.group(1))] = action['content']
        if not replacements:
            return page_html
        try:
            fragment = self._parse_html_fragment(page_html)
            children = [el for el in fragment if isinstance(el.tag, str)]
            for position, content in replacements.items():
                if 1 <= position <= len(children):
                    old = children[position - 1]
                    old.getparent().replace(old, lxml_html.fragment_fromstring(content))
            return self._serialize_html_fragment(fragment)
        except (lxml_etree.ParserError, ValueError):
            _logger.warning("could not merge section replacements; later pass runs on pre-merge HTML")
            return page_html

    @api.model
    def _parse_refinement_response(self, response):
        text = get_text_from_parts(response).strip()
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text)  # some models fence structured output
        return json.loads(text)

    @api.model
    def _refinement_one_shot(self, instructions, message, schema, usage):
        """One schema-constrained refinement call, parsed, retried once (a
        transient parse/decoding failure usually clears on the second attempt).
        Runs at the lowest reasoning level: these are mechanical transforms of an
        already-designed page, and the turn's time budget is worth more."""
        last_error = None
        agent = self.env.ref('ai_website.ai_agent_website_builder', raise_if_not_found=False)
        for attempt in (1, 2):
            try:
                response = self.env['ai.session']._get_direct_response(
                    instructions=instructions, message=message, schema=schema,
                    usage=usage, timeout=_REFINEMENT_PASS_TIMEOUT,
                    agent_id=agent.id,
                )
                return self._parse_refinement_response(response)
            except (UserError, ValueError) as error:  # json.JSONDecodeError is a ValueError
                last_error = error
                _logger.warning("%s: attempt %d/2 failed (%s)", usage, attempt, error)
        raise last_error

    @api.model
    def _refinement_css_pass(self, page_html):
        """Write the page's CSS polish (hover states, colour accents) into
        user_custom_rules.scss via a focused one-shot call."""
        page_path = self.env.context.get('current_view_info', {}).get('website_page', {}).get('location') or '/'
        message = [{'type': 'text', 'text': (
            f"# Page path\n{page_path}\n\n"
            f"# Current user_custom_rules.scss\n{self._read_custom_css()}\n\n"
            f"# Page structure\n{self._html_structure_skeleton(page_html)}"
        )}]
        scss = (self._refinement_one_shot(
            instructions=_CSS_PASS_INSTRUCTIONS, message=message,
            schema=_CSS_PASS_SCHEMA, usage="website_builder_css_polish",
        ).get('scss') or '').strip()
        if not scss:
            return False
        self._save_custom_css(scss)
        return True

    @staticmethod
    def _strip_section_shape(section):
        """Remove any background shape (o_we_shape div + data-oe-shape-data) from
        a section. Returns True if something was removed."""
        removed = False
        for existing in section.findall("./div[@class]"):
            if 'o_we_shape' in (existing.get('class') or '').split():
                section.remove(existing)
                removed = True
        if section.get('data-oe-shape-data') is not None:
            del section.attrib['data-oe-shape-data']
            removed = True
        return removed

    @api.model
    def _refinement_shapes_pass(self, page_html):
        """Decide and inject decorative background shapes. The LLM returns
        placements; the markup is built HERE deterministically and dispatched as
        section-level replace actions. The pass OWNS section shapes: it strips
        any pre-existing one and re-decides, so every touched section ships a
        replace action."""
        css_variables = self.env.context.get('current_view_info', {}).get('website_page', {}).get('css_variables') or {}
        palette_lines = "\n".join(f"- {name}: {value}" for name, value in sorted(css_variables.items())) \
            or "(palette values not available; infer from the o_ccN classes)"

        fragment = self._parse_html_fragment(page_html)
        children = [el for el in fragment if isinstance(el.tag, str)]
        section_positions = [(pos, el) for pos, el in enumerate(children, start=1) if el.tag == 'section']
        sections = [el for _, el in section_positions]
        prestripped_positions = {pos for pos, section in section_positions if self._strip_section_shape(section)}
        page_html = self._serialize_html_fragment(fragment)

        def has_photo_background(section):
            classes = (section.get('class') or '').split()
            if 'parallax' in classes or 'oe_img_bg' in classes or 'background-image' in (section.get('style') or ''):
                return True
            return any('s_parallax_bg_wrap' in (child.get('class') or '') for child in section)

        section_map_lines = []
        section_bg_colors = []
        section_is_sparse = []
        for i, section in enumerate(sections, start=1):
            classes = (section.get('class') or '').split()
            name = next((c for c in classes if c.startswith('ai_')), classes[0] if classes else 'section')
            paddings = '/'.join(c for c in classes if re.fullmatch(r'p[tb]\d+', c)) or 'none'
            if has_photo_background(section):
                section_bg_colors.append(None)
                section_is_sparse.append(False)
                section_map_lines.append(f"{i}. {name} — PHOTO background: no shape on it, no divider facing its edges")
                continue
            cc = next((c[4:] for c in classes if re.fullmatch(r'o_cc[1-5]', c)), None)
            bg_value = css_variables.get(f'o-cc{cc}-bg') if cc else None
            section_bg_colors.append(bg_value if _parse_css_color(bg_value) else None)
            bg_desc = f"bg o_cc{cc} {bg_value or '?'}" if cc else "bg unset"
            text_length = len(re.sub(r'\s+', ' ', section.text_content()).strip())
            image_count = len(section.findall('.//img')) + len(
                [el for el in section.iter() if 'background-image' in (el.get('style') or '')])
            density = 'SPARSE' if text_length < 200 and not image_count else 'dense'
            section_is_sparse.append(density == 'SPARSE')
            section_map_lines.append(
                f"{i}. {name} — {bg_desc} — {density} content ({text_length} text chars, {image_count} image(s)) — padding {paddings}")

        section_map = "\n".join(section_map_lines)
        message = [{'type': 'text', 'text': (
            "# Mood\nInfer the page's mood from the palette and copy; pick the shape family that fits.\n\n"
            f"# Active palette (resolved CSS variables)\n{palette_lines}\n\n"
            f"# Page map (top-level sections, in order)\n{section_map}\n\n"
            f"# Page structure\n{self._html_structure_skeleton(page_html)}"
        )}]
        placements = self._refinement_one_shot(
            instructions=_SHAPES_PASS_INSTRUCTIONS, message=message,
            schema=_SHAPES_PASS_SCHEMA, usage="website_builder_shapes",
        ).get('placements') or []
        if not placements and not prestripped_positions:
            return [], 0

        placed_positions = set()
        claimed_boundaries = set()
        for placement in placements:
            key = placement.get('shape') or ''
            shape_info = _SHAPE_REGISTRY.get(key)
            index = placement.get('section_index')
            if shape_info is None or not isinstance(index, int) or not (1 <= index <= len(section_positions)):
                continue
            position, section = section_positions[index - 1]
            if position in placed_positions or has_photo_background(section):
                continue
            # A centred shape is a backdrop: on a dense section it lands under the text.
            if 'center' in shape_info['position'] and not section_is_sparse[index - 1]:
                _logger.info("shapes pass: %s is a backdrop and section %d is dense, skipping it", key, index)
                continue
            slots = shape_info['slots']

            colors = {
                slot: value
                for slot, value in (placement.get('colors') or {}).items()
                if re.fullmatch(r'c[1-5]', slot or '') and int(slot[1]) in slots
                and re.fullmatch(r'o-color-[1-5]', value or '')
            }
            for slot_number in slots:
                colors.setdefault(f'c{slot_number}', f'o-color-{slot_number}')
            flip = 'x' if placement.get('flip') in ('x', 'xy') else None
            edge = placement.get('edge') if placement.get('edge') in ('top', 'bottom') else None
            natural_position = shape_info['position']
            background_position = None
            if edge == 'top' and 'top' not in natural_position:
                flip = 'xy' if flip == 'x' else 'y'
                background_position = '50% 0%'
            elif edge == 'bottom' and 'top' in natural_position:
                flip = 'xy' if flip == 'x' else 'y'
                background_position = '50% 100%'
            anchored_edge = edge or ('top' if 'top' in natural_position else 'bottom')

            if 'clearance' in shape_info:
                neighbor_list_index = (index - 2) if anchored_edge == 'top' else index
                neighbor = sections[neighbor_list_index] if 0 <= neighbor_list_index < len(sections) else None
                if neighbor is not None and has_photo_background(neighbor):
                    continue
                boundary = (index - 1) if anchored_edge == 'top' else index  # gap below section N
                if boundary in claimed_boundaries:
                    continue
                facing_color = section_bg_colors[neighbor_list_index] if neighbor is not None else None
                if not facing_color:
                    continue
                current_rgb = _parse_css_color(section_bg_colors[index - 1])
                facing_rgb = _parse_css_color(facing_color)
                if current_rgb and facing_rgb:
                    contrast = sum((a - b) ** 2 for a, b in zip(current_rgb, facing_rgb)) ** 0.5
                    if contrast < _MIN_DIVIDER_BG_CONTRAST:
                        continue
                claimed_boundaries.add(boundary)
                # Paint EVERY slot the facing colour (else layered dividers leak
                # their default accents).
                for s in slots:
                    colors[f'c{s}'] = facing_color

            # A slot left as `o-color-N` is fine: the shape controller resolves the token itself.
            colors = {slot: (css_variables.get(value) or value if re.fullmatch(r'o-color-[1-5]', value) else value)
                      for slot, value in colors.items()}
            if clearance := shape_info.get('clearance'):
                _bump_edge_padding(section, anchored_edge, min(256, -(-clearance // 8) * 8))
            placed_positions.add(position)

            params = dict(sorted(colors.items()))
            if flip:
                params['flip'] = flip
            query = '&'.join(f"{name}={quote(str(value), safe='')}" for name, value in params.items())
            url = f"/html_editor/shape/html_builder/{key}.svg" + (f"?{query}" if query else "")
            style = f"background-image: url('{url}');"
            if background_position:
                style += f" background-position: {background_position};"

            shape_div = lxml_html.fragment_fromstring(
                f'<div class="o_we_shape o_html_builder_{key.replace("/", "_")} o_shape_show_mobile" style="{style}"></div>')
            section.insert(0, shape_div)
            shape_data = {'shape': f'html_builder/{key}', 'showOnMobile': True}
            if colors:
                shape_data['colors'] = colors
            if flip:
                shape_data['flip'] = list(flip)
            section.set('data-oe-shape-data', json.dumps(shape_data).replace('"', "'"))

        position_to_section = dict(section_positions)
        actions = []
        for position in sorted(prestripped_positions | placed_positions):
            section = position_to_section[position]
            section.tail = None
            actions.append({
                'zone': 'main', 'mode': 'replace',
                'selector': f'section:nth-child({position})',
                'content': lxml_html.tostring(section, encoding='unicode'),
            })
        return actions, len(placed_positions)
