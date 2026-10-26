"""Shared appearance catalog and strict theme validation."""
import re

from werkzeug.exceptions import BadRequest

LAYOUTS = ('simple-1', 'simple-2')
COLORS = (
    ('orange', '橙色', 'Orange', '#fa7d4b'),
    ('red', '红色', 'Red', '#d94a45'),
    ('purple', '紫色', 'Purple', '#8550ad'),
    ('blue', '蓝色', 'Blue', '#3f67c8'),
    ('navy', '深蓝', 'Navy', '#293d78'),
    ('green', '绿色', 'Green', '#488b35'),
)
APPEARANCES = [
    {'id': f'{layout}-{color}', 'name': f'简约{number} · {name}',
     'name_en': f'Simple {number} · {name_en}', 'layout': layout, 'accent': accent}
    for number, layout in enumerate(LAYOUTS, 1)
    for color, name, name_en, accent in COLORS
]


def validate_theme(value):
    """Normalize older accent-only themes and reject untrusted CSS values."""
    if not isinstance(value, dict) or set(value) - {'layout', 'accent'}:
        raise BadRequest('Expected a theme with layout and accent fields only.')
    layout, accent = value.get('layout', 'simple-1'), value.get('accent', '#fa7d4b')
    if not isinstance(layout, str) or layout not in LAYOUTS:
        raise BadRequest('Unknown appearance layout.')
    if not isinstance(accent, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', accent):
        raise BadRequest('Accent must be a six-digit hexadecimal color.')
    return {'layout': layout, 'accent': accent.lower()}
