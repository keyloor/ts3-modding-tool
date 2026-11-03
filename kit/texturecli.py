"""Texture workspaces and pack creation from the console."""
import json
import struct
import sys
import traceback
import zipfile
import zlib

from modcli import Parser
from modfile import ModError
import texpack


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = '--json' in argv
    argv = [a for a in argv if a != '--json']
    p = Parser(prog='ts3 textures', description='Export PNG textures, edit them, build a mod pack.')
    actions = p.add_subparsers(dest='action', required=True)
    s = actions.add_parser('dump'); s.add_argument('archive', nargs='+'); s.add_argument('--member')
    s.add_argument('--shared', action='store_true', help='one editable PNG for identical DDS textures in selected archives')
    s.add_argument('--game'); s.add_argument('--out', required=True)
    s = actions.add_parser('build'); s.add_argument('workspace'); s.add_argument('--out', required=True)
    s.add_argument('--game'); s.add_argument('--id', required=True); s.add_argument('--name', required=True)
    s.add_argument('--author', required=True); s.add_argument('--version', default='1.0.0')
    command, data, error, status = 'textures', None, None, 0
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    try:
        a = p.parse_args(argv)
        command += '.' + a.action
        from kit import find_game, KitError
        try:
            game = a.game or find_game()
        except KitError as e:
            raise ModError(str(e), 'game_not_found') from e
        if a.action == 'dump':
            data = texpack.dump(game, a.archive, a.out, a.member, shared=a.shared)
        else:
            data = texpack.build(game, a.workspace, a.out, mod_id=a.id, name=a.name, author=a.author, version=a.version)
    except ModError as e:
        status = 2 if e.code == 'invalid_arguments' else 3
        error = dict(code=e.code, message=str(e))
    except (OSError, ValueError, KeyError, IndexError, struct.error, zipfile.BadZipFile, zlib.error) as e:
        status, error = 3, dict(code='io_error' if isinstance(e, OSError) else 'invalid_data', message=str(e))
    except KeyboardInterrupt:
        status, error = 130, dict(code='interrupted', message='Interrupted.')
    except Exception as e:
        status, error = 5, dict(code='internal_error', message=str(e))
        traceback.print_exc(file=sys.stderr)
    if as_json:
        print(json.dumps(dict(schema_version=1, ok=status == 0, command=command, data=data, error=error), ensure_ascii=False))
    elif data is not None:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    if error and not as_json:
        print('error [%s]: %s' % (error['code'], error['message']), file=sys.stderr)
    return status
