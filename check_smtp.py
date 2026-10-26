"""Check SMTP connectivity; optionally authenticate, never send a message."""
import argparse
import json
import smtplib
import ssl
from pathlib import Path

from smtp_config import get_smtp_config

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--connect-only', action='store_true', help='Do not authenticate')
args = parser.parse_args()
settings_file = Path(__file__).with_name('smtp-settings.json')
settings = json.loads(settings_file.read_text(encoding='utf-8-sig'))
try:
    if type(settings.get('ssl')) is not bool or type(settings.get('starttls')) is not bool or settings['ssl'] == settings['starttls']:
        raise ValueError('Choose exactly one secure SMTP transport')
    if not args.connect_only:
        get_smtp_config(settings_file.with_name('smtp-settings.json'))
        if not settings.get('username') or not settings.get('password'):
            raise ValueError('Fill in username and password in the private SMTP settings file')
    context = ssl.create_default_context()
    if settings['ssl']:
        server = smtplib.SMTP_SSL(settings['server'], settings['port'], timeout=20, context=context)
    else:
        server = smtplib.SMTP(settings['server'], settings['port'], timeout=20)
    with server:
        server.ehlo()
        if settings['starttls']:
            server.starttls(context=context)
            server.ehlo()
        if not args.connect_only:
            server.login(settings['username'], settings['password'])
    print('SMTP secure connection OK.' if args.connect_only else 'SMTP authentication OK. No email sent.')
except Exception as error:
    print(f'SMTP check failed: {type(error).__name__}. Check the private settings and network access.')
    raise SystemExit(1) from None
