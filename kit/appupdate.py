"""Shared application-version check; independent of the game and installed mods."""
import loaderprefs
import modfile
import modupdate
from about import TOOL, VERSION

REPOSITORY = 'keyloor/ts3-modding-tool'
RELEASES = 'https://github.com/%s/releases/latest' % REPOSITORY


def check(force=False, *, fetch=modupdate.fetch_latest, now=None):
    cache = loaderprefs.location().with_suffix('.app-updates.json')
    metadata = {'id': 'ts3.application', 'name': TOOL, 'version': modfile.version(VERSION),
                'update': {'github': REPOSITORY}}
    result = modupdate.check([metadata], str(cache), force=force, fetch=fetch, now=now)[0]
    if not result['latest'] and not result['error']:
        result['error'] = 'The latest release does not have a supported version number.'
    # Always open our official release page, never a URL supplied by cached metadata.
    result['url'] = RELEASES
    return result
