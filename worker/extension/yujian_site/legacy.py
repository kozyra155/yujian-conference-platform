"""Legacy exports must obey website withdrawal before native attachment permissions."""
from indico.web.http_api import HTTPAPIHook
from indico.web.http_api.hooks.file import FileHook
from . import YujianSitePlugin


class WebsiteFileHook(FileHook):
    def _has_access(self, user):
        event = self._attachment.folder.event
        if YujianSitePlugin.instance.is_draft(event) and not event.can_manage(user):
            return False
        return super()._has_access(user)


def configure_exports():
    # Native export cache reads precede ACL checks, so they cannot honor immediate withdrawal.
    HTTPAPIHook.NO_CACHE = True
    HTTPAPIHook.HOOK_LIST[:] = [WebsiteFileHook if hook is FileHook else hook for hook in HTTPAPIHook.HOOK_LIST]
