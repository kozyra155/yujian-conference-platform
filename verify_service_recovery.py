"""Check restart policy and local availability without printing runtime secrets."""
import json
import subprocess
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parent
compose = ['docker', 'compose', '-p', 'yujian-indico-v1']
result = subprocess.run(compose + ['config', '--format', 'json'], cwd=root,
                        capture_output=True, text=True, encoding='utf-8', timeout=20)
assert result.returncode == 0, 'Compose configuration could not be validated.'
services = json.loads(result.stdout)['services']
expected = {'indico-web', 'indico-celery', 'indico-celery-beat', 'indico-redis', 'indico-postgres', 'indico-nginx'}
assert all(services[name].get('restart') == 'unless-stopped' for name in expected), 'All website services must restart after the Docker engine recovers.'
result = subprocess.run(compose + ['ps', '--all', '--format', 'json'], cwd=root,
                        capture_output=True, text=True, encoding='utf-8', timeout=20)
assert result.returncode == 0, 'Docker runtime is unavailable.'
containers = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
assert {item['Service'] for item in containers if item['State'] == 'running'} == expected, 'Website services are not all running.'
for item in containers:
    policy = subprocess.run(['docker', 'inspect', '--format', '{{.HostConfig.RestartPolicy.Name}}', item['Name']],
                            capture_output=True, text=True, encoding='utf-8', timeout=10)
    assert policy.returncode == 0 and policy.stdout.strip() == 'unless-stopped', 'Runtime restart policy differs from Compose.'
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
checks = []
for url in ('http://localhost:12880/', 'http://192.168.2.36:12880/',
            'http://192.168.2.36:12880/login/', 'http://192.168.2.36:12880/event/61/'):
    with opener.open(url, timeout=15) as response:
        assert response.status == 200 and response.read(), 'An entry page is unavailable.'
        checks.append({'url': url, 'status': response.status})
print(json.dumps({'passed': True, 'services': len(expected), 'automatic_restart': True, 'http': checks}))
