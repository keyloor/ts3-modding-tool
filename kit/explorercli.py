"""Game explorer commands, with the same JSON envelope as the mod manager."""
import json
import struct
import sys
import traceback
import zipfile
import zlib

from explorer import Browser, KINDS
from modcli import Parser
from modfile import ModError


def parser():
    p = Parser(prog='ts3 explore', description='Browse game assets without modifying them.')
    sub = p.add_subparsers(dest='action', required=True)
    for action in ('index', 'list', 'inspect', 'extract', 'preview', 'glb', 'audio'):
        s = sub.add_parser(action)
        s.add_argument('--game', help='game directory (otherwise Steam detection)')
        if action in ('index', 'list'):
            s.add_argument('--refresh', action='store_true', help='rebuild cached ZIP directories')
        if action == 'list':
            s.add_argument('--query', default='')
            s.add_argument('--kind', choices=KINDS)
            s.add_argument('--limit', type=int, default=200)
            s.add_argument('--offset', type=int, default=0)
        if action in ('inspect', 'extract', 'preview', 'glb', 'audio'):
            s.add_argument('path', help='relative game path, e.g. assets/characters/woody/woody.zip')
            s.add_argument('--member', help='member inside a ZIP; omit to inspect/extract the whole archive')
        if action in ('extract', 'preview', 'glb', 'audio'):
            s.add_argument('--out', required=True, help='new directory outside the game (must not exist)')
        if action == 'audio':
            s.add_argument('--track', type=int, default=0, help='sample index from explore inspect')
            s.add_argument('--seconds', type=float, default=30, help='decode from start, at most 120 seconds')
            s.add_argument('--play', action='store_true', help='play exported WAV; Ctrl+C stops playback')
    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = '--json' in argv
    argv = [a for a in argv if a != '--json']
    command, data, error, status = 'explore', None, None, 0
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    try:
        a = parser().parse_args(argv)
        command += '.' + a.action
        if a.action == 'list' and (a.offset < 0 or not 1 <= a.limit <= 10000):
            raise ModError('Use offset >= 0 and limit between 1 and 10000.', 'invalid_arguments')
        from kit import find_game, KitError
        try:
            game = a.game or find_game()
        except KitError as e:
            raise ModError(str(e), 'game_not_found') from e
        b = Browser(game)
        if a.action in ('index', 'list'):
            index = b.index(a.refresh)
            rows = b.search(index, a.query, a.kind) if a.action == 'list' else b.search(index)
            data = dict(game=str(b.game), total=len(rows), files=len(index['files']),
                        reused=index['reused'], errors=index['errors'])
            if a.action == 'list':
                data.update(items=rows[a.offset:a.offset + a.limit], offset=a.offset,
                            next_offset=a.offset + a.limit if a.offset + a.limit < len(rows) else None)
        elif a.action == 'inspect':
            data = b.inspect(a.path, a.member)
        elif a.action == 'glb':
            data = b.export_glb(a.path, a.member, a.out)
        elif a.action == 'audio':
            import audiobank
            data = audiobank.export(b, a.path, a.member, a.out, a.track, a.seconds)
            if a.play:
                import time
                from pathlib import Path
                player = audiobank.Player()
                try:
                    player.play((Path(data['output'])/'sample.wav').read_bytes())
                    time.sleep(data['decoded_seconds'])
                finally: player.stop()
        else:
            data = b.export(a.path, a.member, a.out, preview=a.action == 'preview')
    except ModError as e:
        status = 2 if e.code == 'invalid_arguments' else 3
        error = dict(code=e.code, message=str(e))
    except (OSError, ValueError, zipfile.BadZipFile, struct.error, zlib.error, IndexError, KeyError) as e:
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
