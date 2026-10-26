"""Create an isolated UI test fixture; never send email or create an account."""
import json
from pathlib import Path

from indico.web.flask.app import make_app
from indico.web.flask.util import url_for
from indico.util.signing import secure_serializer

app = make_app()
with app.test_request_context(base_url='http://192.168.2.36:12880'):
    token = secure_serializer.dumps('register-ui-test@yujian.example', salt='register-email')
    url = url_for('auth.register', token=token, _external=True)
    Path('/tmp/register-preview.json').write_text(json.dumps({'url': url}), encoding='utf-8')
print('Registration UI fixture prepared. No message sent and no account created.')
