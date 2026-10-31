# Contributing to Toy Story 3 Modding Tool

Thanks for wanting to help. Bug reports, ideas, fixes, translations and new sections (music, textures...) are all
welcome.

## How

1. **An idea or a bug**: open an issue. For a bug, say what you did, attach the project's `report.txt` (or the Log tab)
   and the preview images, and say which character and what kind of model (rigged FBX / OBJ, where it comes from).
2. **A change**: fork the repository, make a branch for it (`fix/jessie-material`, `feature/arms-down-preview`...),
   and open a pull request to `main`. Keep one change per pull request; describe what it changes and how you checked
   it. The maintainer (keyloor) reviews and merges.
3. Regular contributors can be given write access to push branches here directly; ask in an issue.

## Rules

- **No game files** in the repository or in pull requests: no `.zip`, `.oct`, `.vbuf`, `.ibuf`, DDS or anything
  extracted from Toy Story 3. The tool reads them from each user's own copy.
- **No models or textures you have no right to share.** Test with any model you like, but don't commit it; describe it
  in the pull request instead (and attach previews).
- **Your own code.** Don't copy code from other projects unless its license allows it under the GPL v3 and you say so
  in the pull request and in `docs/CREDITS.md`.
- **Keep the attribution.** "Toy Story 3 Modding Tool by keyloor" stays where the program shows it (see `NOTICE.md`).
  Add yourself to `docs/CREDITS.md` in your pull request.
- By sending a pull request you agree that your contribution is licensed under the GPL v3 with the terms in
  `NOTICE.md`, like the rest of the tool.

## Code

- Python 3.12, with only `numpy`, `Pillow` and `tkinter`. A new dependency makes the `.exe` bigger and is one more
  license to ship: discuss it in an issue first.
- Read `CLAUDE.md` first: how the pieces fit, the decisions behind them, and the checks.
- Match the code around you: the same naming, short docstrings that say what something is for and why, comments
  only where the reason isn't obvious.
- Every text the window shows goes in `kit/app.py`'s `TEXT`, in Spanish (`es`) and English (`en`).
- `tools/` is shared code (game formats, converter, installer). A change there must not change what it produces for
  maps that already work: add new behaviour as an option whose default is the old behaviour.

## Checks before a pull request

There are no unit tests; these are the checks:

1. **The `.oct` reads back the same**: `python -I tools/rt.py <project>/out/<character>/<character>.oct` prints
   `byte-exact` (`kit.py make` does it for you and stops if not).
2. **Look at the previews** (`previews/body.png`, `previews/face.png`) and attach them to the pull request.
3. **If you touched `tools/`**: convert a model before and after your change and compare the output files byte for
   byte (`fc /b` on Windows); they must be identical unless changing them was the point.
4. **If you touched the window**: open it (`python -I kit/app.py`) in both languages (menu Idioma / Language).
5. **In game**: say whether you tried it in the game (and how it looked). A preview can look right while the game,
   which animates with the arms down, shows a problem.

## Run from source

```
pip install numpy pillow
python -I kit/app.py                 # the window
python -I kit/kit.py --help          # the command line
python -I kit/build_kit.py           # the .exe + release folder (needs: pip install pyinstaller)
```

---

**Español.** Para aportar: abre un *issue* con la idea o el error, o haz un *fork*, crea una rama para tu cambio y
manda un *pull request* a `main`. Reglas: nada de archivos del juego, ni modelos o texturas que no puedas compartir;
código propio; se mantiene «Toy Story 3 Modding Tool by keyloor» (ver `NOTICE.md`); tu aporte queda bajo la misma
licencia (GPL v3 + `NOTICE.md`). Antes del *pull request*: `rt.py` debe decir `byte-exact`, adjunta las vistas previas,
y si tocaste `tools/`, comprueba que lo que ya funcionaba sale idéntico. Los textos de la ventana van en español e
inglés.
