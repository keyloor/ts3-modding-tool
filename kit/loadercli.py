"""Player-loader console entry point. Same mod-manager protocol, no authoring dependencies."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gamepaths
import modcli


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == 'mods':
        args.pop(0)
    return modcli.main(args, game_resolver=gamepaths.find_game)


if __name__ == '__main__':
    raise SystemExit(main())
