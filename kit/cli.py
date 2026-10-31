"""Console entry point for people and AI agents; never creates a window."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == 'mods':
        import modcli
        return modcli.main(argv[1:])
    import kit
    return kit.main(argv)


if __name__ == '__main__':
    raise SystemExit(main())
