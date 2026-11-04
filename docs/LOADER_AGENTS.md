# Toy Story 3 Mod Loader — agent instructions

Toy Story 3 Modding Tool by keyloor. This player application shares the mod manager,
package schema, registry and backups with the authoring application. Do not migrate or reset them.

Use `TS3 Mod Loader CLI.exe mods capabilities --json` to discover the protocol. From source:
`python -I kit/loadercli.py mods capabilities --json`. Commands match the Modding Tool:
inspect, plan, install, list, show, verify, remove, order, recover, updates. The `mods` prefix is optional.

Pass `--game GAME` explicitly. Read `mods inspect PACKAGE`, then `mods plan PACKAGE` and
review its files. When authorized, install using `--expect TICKET`. Removal also supports
`--dry-run` and `--expect TICKET`. Game must be closed for mutations. Use temporary game
folders and `TS3TOOL_SETTINGS` for tests; never alter the user's game to test the program.

JSON: `{schema_version: 1, ok, command, data, error: {code, message}}`. Exit 0 success,
2 arguments, 3 refused operation, 4 failed verification, 5 unexpected error, 130 interrupted.
All operations are noninteractive. Updates only checks release metadata, never downloads.

To replace a package with the same ID, review `mods plan PACKAGE --replace --game GAME --json`,
then `mods install PACKAGE --replace --game GAME --expect TICKET --json` within the authorized scope.
Read `replaces` (installed metadata), `restores` (retired targets) and all `files` before applying.
Original backups are preserved; recovery returns the previously installed version. Same-version rebuilds
and compatible downgrades are allowed. `dependent_version` blocks incompatible dependents. A different ID
does not replace the old one. Never remove the old mod first just to bypass a rejected replacement.

The Loader does not convert characters, edit textures or provide model previews. Use
Toy Story 3 Modding Tool for those. Package constraints are documented in docs/MOD_FORMAT.md.
Do not delete backups or bypass conflicts. Never claim a mod works in game from file checks alone.

Use `mods plan/install PACKAGE --layer` to explicitly share new target files. Read `order`, `shared` and
`files` in the plan. `mods order` only reads; `mods order ID... --dry-run` reviews every installed ID once
from lowest to highest, then `mods order ID... --expect TICKET` applies it. Last wins on matching members
or whole files. Distinct ZIP patch members compose; a coinciding OCT is replaced whole, without merging
its individual textures. Same-ID replacement preserves position; removal reconstructs the remaining layers.
Current apps migrate installed registry 1 to 2 only on a confirmed layered operation; package/JSON schema
stays 1. Never migrate manually or use old binaries to edit layered records. Payload snapshots/original
backups stay in objects/. Limits: 2 GiB new snapshots/rebuilt content per operation. Verification includes
all payloads for a target; hidden layers can be valid even when another layer determines the visible result.

Both GUIs use modview.py for human verification reports and session-only results; refresh invalidates them.
Unknown statuses and damaged/missing hidden-layer data must never look verified. The Loader prioritizes health
warnings over update notices. Raw diagnostics remain in Technical details. The equivalent CLI is unchanged:
`mods verify ID --game GAME --json`; inspect per-file status, backup_status and layers[].status, not just visible
content. This checks files, not in-game appearance. Tests: test_modview.py and test_manager_controls.py.
Selected-mod description/files use scrollable tabs; More holds View result and an available update page.
Report tables use short statuses; selected-file details keep the full explanation.
