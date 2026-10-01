# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from markupsafe import Markup

from odoo import _, api, models

_USER_WEBSITE_VALUES_URL = '/website/static/src/scss/options/user_values.scss'
_USER_COLOR_PALETTE_URL = '/website/static/src/scss/options/colors/user_color_palette.scss'

_HEX_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')

_CC_PRESET_SLOTS = frozenset({'bg', 'text', 'headings', 'link', 'btn-primary', 'btn-secondary'})

_BRAND_FONTS = frozenset({
    'Inter', 'Poppins', 'Montserrat', 'Work Sans', 'DM Sans', 'Manrope',
    'Space Grotesk', 'Sora', 'Archivo', 'Outfit', 'Plus Jakarta Sans',
    'Roboto', 'Open Sans', 'Lato', 'Nunito Sans', 'Karla',
    'Playfair Display', 'Lora', 'Cormorant Garamond', 'DM Serif Display',
    'Libre Baskerville', 'Fraunces', 'Bitter', 'Spectral',
    'Syne', 'Bricolage Grotesque', 'Unbounded',
})

_CORNER_PRESETS = {
    'sharp': {'btn-border-radius': '0', 'btn-border-radius-sm': '0',
              'btn-border-radius-lg': '0', 'input-border-radius': '0'},
    'subtle': {'btn-border-radius': '0.25rem', 'btn-border-radius-sm': '0.2rem',
               'btn-border-radius-lg': '0.3rem', 'input-border-radius': '0.25rem'},
    'rounded': {'btn-border-radius': '0.75rem', 'btn-border-radius-sm': '0.6rem',
                'btn-border-radius-lg': '1rem', 'input-border-radius': '0.6rem'},
    'pill': {'btn-border-radius': '2rem', 'btn-border-radius-sm': '2rem',
             'btn-border-radius-lg': '2rem', 'input-border-radius': '2rem'},
}


def _shadow_tier(infix, offset_y, blur, alpha):
    base = 'box-shadow' + (f'-{infix}' if infix else '')
    return {
        f'{base}-color': f'rgba(0, 0, 0, {alpha})',
        f'{base}-offset-x': '0',
        f'{base}-offset-y': offset_y,
        f'{base}-blur-radius': blur,
        f'{base}-spread-radius': '0',
    }


def _shadow_preset(normal, small, large):
    return {**_shadow_tier('', *normal), **_shadow_tier('sm', *small), **_shadow_tier('lg', *large)}


_SHADOW_PRESETS = {
    'none': _shadow_preset(('0', '0', '0'), ('0', '0', '0'), ('0', '0', '0')),
    'flat': _shadow_preset(('0.125rem', '0.25rem', '0.08'), ('0.0625rem', '0.125rem', '0.06'),
                           ('0.25rem', '0.5rem', '0.1')),
    'soft': _shadow_preset(('0.5rem', '1.5rem', '0.1'), ('0.125rem', '0.375rem', '0.08'),
                           ('1rem', '2.5rem', '0.14')),
    'dramatic': _shadow_preset(('1rem', '2rem', '0.18'), ('0.25rem', '0.5rem', '0.12'),
                               ('1.75rem', '3.5rem', '0.28')),
}


class AIWebsiteService(models.AbstractModel):
    _inherit = 'ai.website.service'

    @api.model
    def _write_scss_customization(self, url, values):
        self.env['website.assets'].with_context(
            website_id=self._current_website().id,
        ).make_scss_customization(url, values)

    @api.model
    def _read_scss_customization(self, assets, url):
        """Read back the key/value pairs `make_scss_customization` wrote into `url`,
        falling back to the uncustomized file — same fallback the writer itself
        uses — so a site that was never customized reads as empty, not an error."""
        custom_url = assets._make_custom_asset_url(url, 'web.assets_frontend')
        content = assets._get_content_from_url(custom_url) or assets._get_content_from_url(url)
        return dict(re.findall(r"'([\w-]+)':\s*([^,\n]+),", content.decode('utf-8')))

    @api.model
    def _get_current_brand_kit(self):
        """Describe the site's current palette and fonts — the theme's defaults
        if "Apply Brand Kit" was never called — so the agent can match new pages
        to what's actually live instead of guessing or reapplying it from scratch."""
        assets = self.env['website.assets'].with_context(website_id=self._current_website().id)
        colors = self._read_scss_customization(assets, _USER_COLOR_PALETTE_URL)
        values = self._read_scss_customization(assets, _USER_WEBSITE_VALUES_URL)

        palette = [colors[f'o-color-{i}'] for i in range(1, 6) if f'o-color-{i}' in colors]
        heading_font = values.get('headings-font', '').strip("'\"")
        body_font = values.get('font', '').strip("'\"")

        palette_text = ', '.join(palette) if palette else "theme default (not customized)"
        fonts_text = (
            f"headings: {heading_font or 'default'}, body: {body_font or 'default'}"
            if heading_font or body_font else "theme default (not customized)"
        )
        return f"Current palette: {palette_text}. Current fonts: {fonts_text}."

    @api.model
    def _build_palette_values(self, o_color_1, o_color_2, o_color_3, o_color_4, o_color_5, cc_presets=None):
        """Validate and assemble the user_color_palette.scss values, or return
        ``(None, error_message)`` on bad input."""
        main_colors = {f'o-color-{i}': c for i, c in enumerate(
            (o_color_1, o_color_2, o_color_3, o_color_4, o_color_5), start=1)}
        for key, value in main_colors.items():
            if not _HEX_COLOR_RE.match(value or ''):
                return None, f"Invalid hex color for {key}: {value!r}. Use a 6-digit hex like '#A1B2C3'."

        values = dict(main_colors)
        for preset in cc_presets or []:
            index = preset.get('index')
            if index not in (1, 2, 3, 4, 5):
                return None, f"Invalid cc_presets entry — 'index' must be an integer 1..5 (got {index!r})."
            for slot, color in preset.items():
                if slot == 'index' or color is None:
                    continue
                if slot not in _CC_PRESET_SLOTS:
                    return None, f"Invalid cc_presets slot {slot!r} on index {index}. Allowed: {sorted(_CC_PRESET_SLOTS)}."
                if not _HEX_COLOR_RE.match(color):
                    return None, f"Invalid hex color for o-cc{index}-{slot}: {color!r}. Use a 6-digit hex like '#A1B2C3'."
                values[f'o-cc{index}-{slot}'] = color
        return values, None

    @api.model
    def _build_typography_values(self, typography):
        """Validate fonts against _BRAND_FONTS and assemble the user_values.scss
        font keys. heading_font + body_font are required together; button_font is
        optional. Empty typography yields ``({}, None)``."""
        if not typography:
            return {}, None
        heading = (typography.get('heading_font') or '').strip()
        body = (typography.get('body_font') or '').strip()
        button = (typography.get('button_font') or '').strip()
        if not heading or not body:
            return None, "typography requires both 'heading_font' and 'body_font'."
        for font in (heading, body, button):
            if font and font not in _BRAND_FONTS:
                return None, f"Unknown font {font!r}. Choose from the brand font catalog: {', '.join(sorted(_BRAND_FONTS))}."
        values = {'font': f"'{body}'", 'headings-font': f"'{heading}'"}
        if button:
            values['buttons-font'] = f"'{button}'"
        google = list(dict.fromkeys(f for f in (heading, body, button) if f))
        values['google-fonts'] = "('" + "', '".join(google) + "')"
        return values, None

    @api.model
    def _build_design_values(self, design):
        """Map the corner/shadow keywords to their theme variables. Empty design
        yields ``({}, None)``."""
        if not design:
            return {}, None
        values = {}
        corners = (design.get('corners') or '').strip().lower()
        if corners:
            if corners not in _CORNER_PRESETS:
                return None, f"Unknown corners preset {corners!r}. Allowed: {', '.join(sorted(_CORNER_PRESETS))}."
            values.update(_CORNER_PRESETS[corners])
        shadow = (design.get('shadow') or '').strip().lower()
        if shadow:
            if shadow not in _SHADOW_PRESETS:
                return None, f"Unknown shadow preset {shadow!r}. Allowed: {', '.join(sorted(_SHADOW_PRESETS))}."
            values.update(_SHADOW_PRESETS[shadow])
        return values, None

    @api.model
    def _brand_kit_confirmation_message(self, palette_values, typography, design):
        """The site-wide warning the user must accept before the brand kit is written."""
        items = []
        if palette_values:
            swatches = Markup('').join(
                # `background-color`, not `background`: the mail sanitizer drops the shorthand.
                Markup('<span style="display:inline-block;width:14px;height:14px;margin-right:3px;'
                       'vertical-align:middle;border:1px solid rgba(0,0,0,.2);border-radius:3px;'
                       'background-color:%s"></span>') % palette_values[f'o-color-{i}']
                for i in range(1, 6)
            )
            items.append(Markup('%s %s') % (_("A new colour palette:"), swatches))
        if typography and typography.get('heading_font'):
            items.append(_(
                "New fonts: %(heading)s for the titles, %(body)s for the text.",
                heading=typography['heading_font'], body=typography['body_font'],
            ))
        if style := ", ".join(part for part in (
                (design or {}).get('corners'), (design or {}).get('shadow')) if part):
            items.append(_("A new corner and shadow style: %s.", style))
        return Markup('<p>%s</p><ul>%s</ul><p><b>%s</b></p>') % (
            _("Before I start, I'd like to set the overall look of the site:"),
            Markup('').join(Markup('<li>%s</li>') % item for item in items),
            _("This applies to every page of your website, not only this one. Shall I go ahead?"),
        )
