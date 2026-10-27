"""Verify application SMTP configuration and authentication without sending mail."""
import json

from indico.core.config import config
from indico.vendor.django_mail import get_connection
from indico.web.flask.app import make_app

app = make_app()
with app.app_context():
    assert config.EMAIL_BACKEND == 'indico.vendor.django_mail.backends.smtp.EmailBackend'
    assert config.SMTP_USE_SSL != config.SMTP_USE_TLS
    assert config.SMTP_USE_CELERY
    assert config.NO_REPLY_EMAIL == config.SMTP_LOGIN
    assert config.SMTP_ALLOWED_SENDERS == {config.SMTP_LOGIN}
    assert config.SMTP_SENDER_FALLBACK == config.SMTP_LOGIN
    try:
        with get_connection() as connection:
            assert connection.connection is not None, 'SMTP connection did not open'
    except Exception as error:
        print(json.dumps({'passed': False, 'error_type': type(error).__name__}))
        raise SystemExit(1) from None
    print(json.dumps({'passed': True, 'backend': config.EMAIL_BACKEND,
                      'server': config.SMTP_SERVER[0], 'port': config.SMTP_SERVER[1],
                      'secure_transport': True, 'authentication': True,
                      'sender_matches_login': True, 'queue_enabled': True,
                      'email_sent': False}))
