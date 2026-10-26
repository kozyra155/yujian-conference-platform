import json
import tempfile
import unittest
from pathlib import Path

from smtp_config import get_smtp_config


class SMTPConfigTests(unittest.TestCase):
    def load(self, data):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'settings.json'
            file.write_text(json.dumps(data), encoding='utf-8')
            return get_smtp_config(file)

    def valid(self):
        return {'enabled': True, 'server': 'smtp.example.com', 'port': 465,
                'ssl': True, 'starttls': False, 'username': 'test@example.com', 'password': 'fixture-only'}

    def test_disabled_keeps_demo_backend(self):
        self.assertEqual(self.load({'enabled': False}), {})

    def test_requires_boolean_switch(self):
        for value in ('true', 'false', 1, 0, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.load({'enabled': value})
        with self.assertRaises(ValueError):
            self.load({})

    def test_authenticated_sender_is_used_for_system_mail(self):
        config = self.load(self.valid())
        self.assertEqual(config['NO_REPLY_EMAIL'], 'test@example.com')
        self.assertEqual(config['SMTP_SENDER_FALLBACK'], 'test@example.com')
        self.assertEqual(config['SMTP_ALLOWED_SENDERS'], {'test@example.com'})
        self.assertTrue(config['SMTP_USE_SSL'])

    def test_rejects_missing_credentials_and_insecure_transport(self):
        for changed in ({'password': ''}, {'username': 'invalid'}, {'port': 0},
                        {'ssl': True, 'starttls': True}, {'ssl': False, 'starttls': False}):
            with self.subTest(changed=list(changed)), self.assertRaises(ValueError):
                self.load(self.valid() | changed)


if __name__ == '__main__':
    unittest.main()
