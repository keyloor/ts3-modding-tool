"""Game discovery shared by the player loader and authoring tool; standard library only."""
import os

GAME_DIR = 'Toy Story 3 Complete Edition'


class GameNotFound(ValueError):
    pass


def steam_libraries():
    roots = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as key:
            roots.append(winreg.QueryValueEx(key, 'SteamPath')[0])
    except (ImportError, OSError):
        pass
    roots += [r'C:\Program Files (x86)\Steam', r'C:\Program Files\Steam']
    libraries = []
    for root in roots:
        libraries.append(root)
        vdf = os.path.join(root, 'steamapps', 'libraryfolders.vdf')
        if os.path.isfile(vdf):
            with open(vdf, encoding='utf-8', errors='replace') as stream:
                for line in stream:
                    fields = line.strip().split('"')
                    if len(fields) >= 4 and fields[1] == 'path':
                        libraries.append(fields[3].replace('\\\\', '\\'))
    return list(dict.fromkeys(libraries))


def find_game(given=None):
    candidates = [given] if given else [os.path.join(lib, 'steamapps', 'common', GAME_DIR) for lib in steam_libraries()]
    for folder in candidates:
        if folder and os.path.isdir(os.path.join(folder, 'assets', 'characters')):
            return os.path.normpath(folder)
    if given:
        raise GameNotFound('%s is not the game folder (it has no assets/characters)' % given)
    raise GameNotFound('the game was not found in Steam\'s folders: give it with --game "<folder of %s>"' % GAME_DIR)
