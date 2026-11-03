"""Rigid mesh workspace CLI; uses the shared machine-readable envelope."""
import json
import sys
import traceback
import struct
import zipfile
import zlib
from modcli import Parser
from modfile import ModError
import meshpack


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = '--json' in argv; argv = [v for v in argv if v != '--json']
    p = Parser(prog='ts3 meshes', description='Edit rigid GLB geometry with preserved or explicit replacement topology; build a mod pack.')
    sub = p.add_subparsers(dest='action', required=True)
    s = sub.add_parser('dump'); s.add_argument('archive'); s.add_argument('--member', required=True)
    s.add_argument('--game'); s.add_argument('--out', required=True)
    s.add_argument('--piece',type=int,help='export only this visible OCT node for topology replacement')
    s = sub.add_parser('pieces');s.add_argument('source',help='mesh workspace, or archive with --member OCT')
    s.add_argument('--member');s.add_argument('--game')
    s = sub.add_parser('build'); s.add_argument('workspace'); s.add_argument('--model')
    s.add_argument('--out', required=True); s.add_argument('--game'); s.add_argument('--id', required=True)
    s.add_argument('--name', required=True); s.add_argument('--author', required=True); s.add_argument('--version', default='1.0.0')
    s.add_argument('--topology', choices=('preserve','replace'), default='preserve',
                   help='preserve original triangles (default), or replace one visible rigid piece with new topology')
    s.add_argument('--piece',type=int,help='visible OCT node to replace; required when the target has several pieces')
    command, data, error, status = 'meshes', None, None, 0
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'): stream.reconfigure(encoding='utf-8')
    try:
        a = p.parse_args(argv); command += '.'+a.action
        from kit import find_game, KitError
        try: game = a.game or find_game()
        except KitError as e: raise ModError(str(e), 'game_not_found') from e
        if a.action == 'dump': data = meshpack.dump(game, a.archive, a.member, a.out,piece=a.piece)
        elif a.action == 'pieces':
            data=meshpack.list_pieces(game,a.source,a.member) if a.member else meshpack.pieces(game,a.source)
        else:
            data = meshpack.build(game, a.workspace, a.out, mod_id=a.id, name=a.name, author=a.author,
                                  version=a.version, model=a.model, topology=a.topology,piece=a.piece)
    except ModError as e:
        status = 2 if e.code == 'invalid_arguments' else 3; error = dict(code=e.code, message=str(e))
    except (OSError, ValueError, KeyError, IndexError, TypeError, struct.error, zipfile.BadZipFile, zlib.error) as e:
        status, error = 3, dict(code='io_error' if isinstance(e, OSError) else 'invalid_data', message=str(e))
    except KeyboardInterrupt:
        status, error = 130, dict(code='interrupted', message='Interrupted.')
    except Exception as e:
        status, error = 5, dict(code='internal_error', message=str(e)); traceback.print_exc(file=sys.stderr)
    if as_json:
        print(json.dumps(dict(schema_version=1, ok=status==0, command=command, data=data, error=error), ensure_ascii=False))
    elif data is not None: print(json.dumps(data, ensure_ascii=False, indent=2))
    if error and not as_json: print('error [%s]: %s' % (error['code'], error['message']), file=sys.stderr)
    return status
