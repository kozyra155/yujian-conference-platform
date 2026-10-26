"""Read private SMTP settings without logging credentials."""
import json
from email.utils import parseaddr
from pathlib import Path


def get_smtp_config(filename):
    settings = json.loads(Path(filename).read_text(encoding='utf-8-sig'))
    if not isinstance(settings, dict) or type(settings.get('enabled')) is not bool:
        raise ValueError('SMTP enabled must be a boolean')
    if not settings['enabled']:
        return {}
    for key in ('server', 'username', 'password'):
        if not isinstance(settings.get(key), str) or not settings[key].strip():
            raise ValueError(f'SMTP settings require {key}')
    username = settings['username'].strip()
    if parseaddr(username)[1] != username or '@' not in username or any(c in username for c in '\r\n'):
        raise ValueError('SMTP username must be a complete email address')
    port = settings.get('port')
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('SMTP port must be between 1 and 65535')
    ssl = settings.get('ssl')
    tls = settings.get('starttls')
    if type(ssl) is not bool or type(tls) is not bool or ssl == tls:
        raise ValueError('Choose exactly one of SSL or STARTTLS')
    return {
        'EMAIL_BACKEND': 'indico.vendor.django_mail.backends.smtp.EmailBackend',
        'SMTP_SERVER': (settings['server'].strip(), port),
        'SMTP_LOGIN': username,
        'SMTP_PASSWORD': settings['password'],
        'SMTP_USE_SSL': ssl,
        'SMTP_USE_TLS': tls,
        'SMTP_TIMEOUT': 20,
        'SMTP_USE_CELERY': True,
        'SMTP_ALLOWED_SENDERS': {username},
        'SMTP_SENDER_FALLBACK': username,
        'NO_REPLY_EMAIL': username,
    }
