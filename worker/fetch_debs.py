"""Download apt's resolved package list concurrently; apt still verifies packages."""
import concurrent.futures
from pathlib import Path
import shlex
import socket
import subprocess
import sys
import urllib.request
import urllib.error

socket.setdefaulttimeout(60)

resolved = subprocess.check_output(['apt-get', '-y', '--print-uris', 'install',
                                    '--no-install-recommends', *sys.argv[1:]], text=True)
packages = [shlex.split(line) for line in resolved.splitlines() if line.startswith("'")]
Path('/var/cache/apt/archives/partial').mkdir(parents=True, exist_ok=True)


def download(package):
    url, name, size, *_ = package
    assert url.startswith('https://deb.debian.org/') and Path(name).name == name
    temporary = Path('/var/cache/apt/archives/partial') / name
    for attempt in range(3):
        try:
            urllib.request.urlretrieve(url, temporary)
            break
        except (urllib.error.URLError, OSError):
            if attempt == 2:
                raise
            print(f'Retrying {name}', flush=True)
    assert temporary.stat().st_size == int(size), f'Incomplete download: {name}'
    temporary.replace(temporary.parent.parent / name)
    print(f'Downloaded {name}', flush=True)


with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    list(pool.map(download, packages))
