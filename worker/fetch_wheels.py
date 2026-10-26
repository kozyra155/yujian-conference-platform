"""Fetch the two large PyPI wheels in ranges and verify official SHA-256 hashes."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import sys
import urllib.error
import urllib.request

directory = Path('/opt/indico/.cache/wheels')
directory.mkdir(parents=True, exist_ok=True)


def checksum(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


for package, version in [('indico', sys.argv[1]), ('indico-fonts', '1.2')]:
    with urllib.request.urlopen(f'https://pypi.org/pypi/{package}/{version}/json', timeout=60) as response:
        metadata = json.load(response)
    wheel = next(item for item in metadata['urls'] if item['filename'].endswith('.whl'))
    name, size, url, expected = wheel['filename'], wheel['size'], wheel['url'], wheel['digests']['sha256']
    if Path(name).name != name or not url.startswith('https://files.pythonhosted.org/'):
        raise ValueError('Unexpected wheel source')
    target = directory / name
    if target.exists() and checksum(target) == expected:
        continue

    def download(index):
        start, end = size * index // 8, size * (index + 1) // 8 - 1
        part = directory / f'{name}.part{index}'
        if part.exists() and part.stat().st_size == end - start + 1:
            return part
        for attempt in range(3):
            try:
                request = urllib.request.Request(url, headers={'Range': f'bytes={start}-{end}'})
                with urllib.request.urlopen(request, timeout=60) as response, part.open('wb') as output:
                    if response.status != 206 or response.headers['Content-Range'] != f'bytes {start}-{end}/{size}':
                        raise ValueError('Server did not honor the byte range')
                    shutil.copyfileobj(response, output)
                if part.stat().st_size != end - start + 1:
                    raise OSError('Incomplete wheel part')
                print(f'{name}: part {index + 1}/8 ready', flush=True)
                return part
            except (urllib.error.URLError, OSError):
                if attempt == 2:
                    raise

    with ThreadPoolExecutor(max_workers=8) as pool:
        parts = list(pool.map(download, range(8)))
    temporary = target.with_suffix('.tmp')
    with temporary.open('wb') as output:
        for part in parts:
            with part.open('rb') as stream:
                shutil.copyfileobj(stream, output)
    if checksum(temporary) != expected:
        temporary.unlink()
        for part in parts:
            part.unlink()
        raise ValueError(f'SHA-256 mismatch: {name}')
    temporary.replace(target)
    for part in parts:
        part.unlink()
    print(f'{name}: official SHA-256 verified', flush=True)
