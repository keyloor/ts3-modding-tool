"""Non-interactive mod-manager CLI. --json emits exactly one versioned response to stdout."""
import argparse
import json
import re
import struct
import sys
import traceback
import zipfile
import zlib

from modfile import ModError, Package
from modstore import Store

COMMANDS = {
    'capabilities': 'Describe commands and the JSON protocol (no game required).',
    'inspect': 'Read package metadata (does not validate game compatibility).',
    'plan': 'Fully validate an installation and return its changes and ticket; do not install.',
    'install': 'Install a package, optionally requiring a previously reviewed ticket.',
    'list': 'List mods registered with this manager.',
    'show': 'Show a registered mod and its tracked files.',
    'verify': 'Check installed files and backups; do not repair them.',
    'remove': 'Remove a registered mod, or preview removal with --dry-run.',
    'recover': 'Restore the state before an interrupted manager operation.',
    'updates': 'Check installed mods with update.github for a newer GitHub release (never downloads).'}
EXIT_CODES = {'success': 0, 'invalid_arguments': 2, 'operation_failed': 3, 'verification_failed': 4,
              'internal_error': 5, 'interrupted': 130}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ModError(message, 'invalid_arguments')


def ticket(value):
    if not re.fullmatch('[0-9a-f]{64}', value):
        raise argparse.ArgumentTypeError('expected a 64-character plan ticket')
    return value


def parser():
    common = Parser(add_help=False)
    common.add_argument('--json', action='store_true', default=argparse.SUPPRESS,
                        help='one UTF-8 JSON response on stdout, including errors')
    p = Parser(prog='ts3 mods', description='TS3 Modding Tool by keyloor — mod manager', parents=[common])
    p.set_defaults(json=False)
    actions = p.add_subparsers(dest='action', required=True)
    for action, help_text in COMMANDS.items():
        sub = actions.add_parser(action, help=help_text, description=help_text, parents=[common])
        if action in ('inspect', 'plan', 'install'):
            sub.add_argument('package', help='package folder or ZIP')
        if action in ('show', 'verify', 'remove'):
            sub.add_argument('id', help='installed mod id from list')
        if action not in ('capabilities', 'inspect'):
            sub.add_argument('--game', help='game folder; agents should pass it explicitly')
        if action == 'updates':
            sub.add_argument('--force', action='store_true', help='ask GitHub now, not the once-a-day cache')
        if action in ('install', 'remove'):
            sub.add_argument('--dry-run', action='store_true', help='validate and describe changes without applying them')
            sub.add_argument('--expect', type=ticket, help='require the ticket returned by plan / remove --dry-run')
    return p


def capabilities():
    return {'protocol_version': 1, 'commands': COMMANDS, 'exit_codes': EXIT_CODES,
            'json_flag': '--json (before or after the command)', 'non_interactive': True,
            'game_scope': 'ts3-pc', 'package_schema_versions': [1],
            'workflow': ['inspect PACKAGE', 'plan PACKAGE --game GAME',
                         'install PACKAGE --game GAME --expect TICKET', 'verify MOD_ID --game GAME',
                         'remove MOD_ID --game GAME --dry-run', 'remove MOD_ID --game GAME --expect TICKET'],
            'limits': ['One registered mod per game file; no force overwrite.',
                       'Game must be closed for mutations.', 'No automatic downloads or GUI interaction.',
                       'plan and verify can create the manager lock file, but do not change game content.']}


def plan_data(plan, game, action):
    result = dict(plan, game=game, action=action, status='planned')
    result['files'] = [dict(r, operation='create' if r['before'] is None else 'delete' if r['after'] is None
                          else 'unchanged' if r['before'] == r['after'] else 'replace') for r in plan['files']]
    return result


def dispatch(a, game_resolver=None):
    if a.action == 'capabilities':
        return capabilities(), 0
    if a.action == 'inspect':
        with Package(a.package) as package:
            return {'metadata': package.metadata, 'package': str(package.source)}, 0
    game = a.game
    if not game:
        if game_resolver is None:
            from kit import find_game
            game_resolver = find_game
        try:
            game = game_resolver()
        except Exception as e:
            raise ModError(str(e), 'game_not_found') from e
    store = Store(game)
    game = str(store.game)
    if a.action == 'list':
        return {'game': game, 'mods': store.list()}, 0
    if a.action == 'updates':
        import modupdate
        return {'game': game, 'updates': modupdate.check(store.list(), str(store.path(modupdate.CACHE)),
                                                         force=a.force)}, 0
    if a.action == 'show':
        mod = next((m for m in store.list() if m['metadata']['id'] == a.id), None)
        if mod is None:
            raise ModError('mod is not installed: ' + a.id, 'not_installed')
        return dict(mod, game=game), 0
    if a.action == 'verify':
        result = dict(store.verify(a.id), game=game)
        return result, 0 if result['valid'] else 4
    if a.action == 'plan' or (a.action == 'install' and a.dry_run):
        return plan_data(store.preview(a.package), game, 'install'), 0
    if a.action == 'remove' and a.dry_run:
        return plan_data(store.preview_remove(a.id), game, 'remove'), 0
    if a.action == 'install':
        return {'game': game, 'status': 'installed', 'metadata': store.install(a.package, expected=a.expect)}, 0
    if a.action == 'remove':
        return {'game': game, 'status': 'removed', 'metadata': store.remove(a.id, expected=a.expect)}, 0
    return {'game': game, 'recovered': store.recover()}, 0


def main(argv=None, game_resolver=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = '--json' in argv
    command = 'mods'
    data = error = None
    status = 0
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    try:
        a = parser().parse_args(argv)
        command = 'mods.' + a.action
        if getattr(a, 'dry_run', False) and a.expect is not None:
            raise ModError('--dry-run and --expect cannot be combined', 'invalid_arguments')
        data, status = dispatch(a, game_resolver)
        if status == 4:
            error = {'code': 'verification_failed', 'message': 'Installed files or backups do not match the registry.'}
    except ModError as e:
        status = 2 if e.code == 'invalid_arguments' else 3
        error = {'code': e.code, 'message': str(e)}
    except (zipfile.BadZipFile, struct.error, zlib.error, UnicodeError, ValueError) as e:
        status, error = 3, {'code': 'invalid_data', 'message': str(e)}
    except OSError as e:
        status, error = 3, {'code': 'io_error', 'message': str(e)}
    except KeyboardInterrupt:
        status, error = 130, {'code': 'interrupted', 'message': 'Operation interrupted; check recovery before retrying.'}
    except Exception as e:
        status, error = 5, {'code': 'internal_error', 'message': str(e) or type(e).__name__}
        traceback.print_exc(file=sys.stderr)
    if as_json:
        print(json.dumps({'schema_version': 1, 'ok': status == 0, 'command': command,
                          'data': data, 'error': error}, ensure_ascii=False))
    else:
        if data is not None:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        if error:
            print('error [%s]: %s' % (error['code'], error['message']), file=sys.stderr)
    return status
