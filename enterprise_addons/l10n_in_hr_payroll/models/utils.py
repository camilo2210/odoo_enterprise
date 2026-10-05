# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re


# Utility methods for Form 138 txt generation
def format_char(value, size=None, default=''):
    value = re.sub(r'[\r\n^]+|\s+', ' ', str(value or default or '')).strip()
    value = value.encode('ascii', 'ignore').decode()
    return value[:size] if size else value


def format_digits(value, size):
    value = re.sub(r'\D', '', str(value or ''))
    return value[-size:] if size and len(value) > size else value


def format_amount(value, precision=2):
    return f'{(value or 0.0):.{precision}f}'


def join_record(record):
    return '^'.join(
        '' if value in (None, False) else str(value)
        for value in record
    )
