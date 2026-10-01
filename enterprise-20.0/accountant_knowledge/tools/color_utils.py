import re


def lighten_color(hex_color, amount=0.2):
    """ Lighten a hex color by mixing it with white.
    Safely returns '#ffffff' if the input is not a valid hex color.
    :param str hex_color: Hex color string, e.g. '#336699' or '336699'.
    :param float amount: How much to lighten (0 = no change, 1 = white. Clamped between 0 and 1).
    :return str: Lightened hex color. """

    default_white = '#ffffff'
    if not isinstance(amount, (int, float)):
        return default_white
    if not isinstance(hex_color, str):
        return default_white

    clamped_amount = max(0.0, min(1.0, float(amount)))
    cleaned_hex = hex_color.lstrip('#')

    if not re.match(r'^([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$', cleaned_hex):
        return default_white

    if len(cleaned_hex) == 3:
        cleaned_hex = ''.join([char * 2 for char in cleaned_hex])
    r, g, b = [int(cleaned_hex[i:i + 2], 16) for i in (0, 2, 4)]

    # Blend with white
    r = int(r + (255 - r) * clamped_amount)
    g = int(g + (255 - g) * clamped_amount)
    b = int(b + (255 - b) * clamped_amount)

    # Convert back to hex
    return f'#{r:02x}{g:02x}{b:02x}'
