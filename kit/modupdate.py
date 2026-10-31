"""Update checks for installed mods: a mod whose mod.json has update.github ("owner/repository") is compared with
that repository's latest GitHub release. Read-only and never downloads anything: it only says that a newer version
exists and where its page is. Each repository is asked at most once a day (cached next to the manager's registry, in
<game>/TS3 Modding Tool/updates.json); a failed request is retried after an hour.

  check(mods, cache_path)   mods as Store.list() gives them -> one dict per mod with update.github
  check(..., fetch=None)    only what the cache already knows (no network; the window's list uses it)
"""
import json, os, time, urllib.request

import modfile

API = 'https://api.github.com/repos/%s/releases/latest'
DAY, RETRY = 86400, 3600
CACHE = 'TS3 Modding Tool/updates.json'


def fetch_latest(repo, timeout=8):
    """the repository's latest release: {'tag', 'url'} (GitHub's public API, no key)"""
    req = urllib.request.Request(API % repo, headers={'Accept': 'application/vnd.github+json',
                                                      'User-Agent': 'TS3-Modding-Tool'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    return {'tag': str(d.get('tag_name') or ''), 'url': str(d.get('html_url') or '')}


def tag_version(tag):
    """'v1.2' or '1.2.0' -> '1.2.0'; None when the tag isn't a plain numeric version"""
    try:
        return modfile.version(tag[1:] if tag[:1] in 'vV' else tag)
    except (modfile.ModError, TypeError):
        return None


def newer(a, b):
    return tuple(map(int, a.split('.'))) > tuple(map(int, b.split('.')))


def check(mods, cache_path=None, force=False, fetch=fetch_latest, now=None):
    now = time.time() if now is None else now
    cache = {}
    if cache_path and os.path.isfile(cache_path):
        try:
            cache = json.load(open(cache_path, encoding='utf-8'))
        except (OSError, ValueError):
            cache = {}
    out = []
    for mod in mods:
        meta = mod.get('metadata', mod)
        repo = (meta.get('update') or {}).get('github')
        if not repo:
            continue
        entry = cache.get(repo)
        if fetch is None and not entry:
            continue
        stale = not entry or now - entry.get('time', 0) >= (RETRY if 'error' in entry else DAY)
        if fetch is not None and (force or stale):
            try:
                entry = dict(fetch(repo), time=now)
            except Exception as e:                       # offline, rate limited, no releases: say so, retry later
                entry = {'time': now, 'error': str(e) or type(e).__name__}
            cache[repo] = entry
        latest = tag_version(entry.get('tag', ''))
        out.append({'id': meta['id'], 'name': meta.get('name', meta['id']), 'installed': meta.get('version'),
                    'repo': repo, 'latest': latest, 'url': entry.get('url') or 'https://github.com/%s/releases' % repo,
                    'update': bool(latest and meta.get('version') and newer(latest, meta['version'])),
                    'error': entry.get('error')})
    if cache_path and fetch is not None:
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=1)
        except OSError:
            pass
    return out
