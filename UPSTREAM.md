Local evaluation based on https://github.com/indico/indico-containers at 8e968191bbb962e74c5356f9658d5ed694d8067a and Indico v3.3.13.

Indico itself is MIT licensed (see LICENSE.indico). The checked-out container examples have no separate LICENSE file; do not assume the application's license covers this repository. This local copy is for evaluation; clarify the example scripts' terms before redistributing them commercially.
Changes: Python slim base, minimal system dependencies, fixed Indico version, no external plugins or Podman, no privileged containers, local ports and private configuration. Not a production deployment.

Build downloads use official Debian HTTPS repositories with apt verification, a small concurrent downloader and persistent caches. The uv build utility is pinned by image digest. Example configurations and automated tests use Indico's in-memory mail backend; the existing local deployment may enable SMTP through excluded private settings.

Local application extensions, branded frontend and verification scripts live in this directory. The sibling upstream checkout is a development reference and is not required inside this source repository. Docker/WSL disks and database/upload backups are not source files and are excluded. See README.md for current features and deployment limits.
