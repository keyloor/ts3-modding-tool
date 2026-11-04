"""Build separate Modding Tool and player Mod Loader packages, with their own executables and ZIPs.

  python build_kit.py              both release folders + ZIPs
  python build_kit.py --local      both test copies under Start Menu/Programs (no ZIPs), with shortcuts
  python build_kit.py --desktop    legacy alias for --local

'Toy Story 3 Modding Tool.exe' (PyInstaller, one folder, no console) + the kit's and the tools' Python source (for the
command line and AI agents), docs, the skill, the license, and the licenses of what the .exe carries inside
(Python, numpy, Pillow, moderngl, glcontext, Tcl/Tk).
"""
import glob, importlib.metadata as md, os, shutil, subprocess, sys, zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
from about import TOOL, VERSION, LOADER, LOADER_CLI

KIT = paths.KIT
TOOLS_USED = ['octlib', 'fbxlib', 'ts3model', 'convert', 'render', 'install', 'build_release', 'zx', 'zls', 'rt',
              'fbxinfo', 'bones5', 'dump', 'texpeek', 'angles', 'skelcmp', 'fmodbank', 'identityfit']
KIT_FILES = ['about', 'paths', 'automap', 'autotex', 'objlib', 'viewer', 'modfile', 'modstore', 'modupdate', 'dropfiles',
             'modcli', 'modlayers', 'modpriorityui', 'modview', 'homeui', 'cli', 'kit', 'app', 'build_kit', 'explorer', 'explorercli', 'explorerui', 'explorerpresent',
             'ddsedit', 'texpack', 'texturecli', 'gltf', 'gltflib', 'identity', 'meshpack', 'meshcli', 'meshtopo', 'audiobank', 'audio_worker', 'gamepaths', 'loaderprefs', 'loader', 'loaderui', 'loadercli']
CLI = 'TS3 Modding CLI'
SHORTCUT = 'Abrir ' + TOOL + '.lnk'


def programs():
    import ctypes
    buf = ctypes.create_unicode_buffer(260)
    result = ctypes.windll.shell32.SHGetFolderPathW(None, 0x02, None, 0, buf)  # per-user CSIDL_PROGRAMS
    if result or not buf.value:
        raise OSError('Could not find the Start Menu Programs folder.')
    return buf.value


def exe_running(folder):
    """is the .exe of that folder open? (its files can't be replaced then)"""
    exes = {os.path.join(folder, name + '.exe').lower() for name in (TOOL, CLI, LOADER, LOADER_CLI)}
    out = subprocess.run(['powershell', '-NoProfile', '-Command',
                          "Get-Process | Where-Object { $_.Path } | ForEach-Object { $_.Path }"],
                         capture_output=True, text=True).stdout.lower()
    return bool(exes.intersection(out.splitlines()))


def local_target(product=TOOL):
    if product not in (TOOL, LOADER):
        raise ValueError('Unknown local build product.')
    base = Path(programs()).resolve()
    dst = base / product
    if dst.is_symlink() or dst.is_junction() or dst.resolve().parent != base:
        raise OSError('The local build target must be the tool folder directly under Start Menu/Programs.')
    return dst


def to_local(rel, product=TOOL):
    """Replace only Programs/<TOOL>, then point its Start menu shortcut at the new exe."""
    dst = str(local_target(product))
    if exe_running(dst):
        sys.exit('%s is open from the Start menu: close it and run this again' % product)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(rel, dst)
    lnk = os.path.join(programs(), 'Abrir ' + product + '.lnk')
    ps = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%s'); $s.TargetPath = '%s'; "
          "$s.WorkingDirectory = '%s'; $s.Description = '%s'; $s.Save()") % (
        lnk.replace("'", "''"), os.path.join(dst, product + '.exe').replace("'", "''"), dst.replace("'", "''"), product)
    subprocess.run(['powershell', '-NoProfile', '-Command', ps], check=True)
    print('local build: %s\nshortcut: %s' % (dst, lnk))


def zip_product(folder):
    zpath = folder + '.zip'
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for base, _, files in os.walk(folder):
            for name in files:
                z.write(os.path.join(base, name), os.path.join(os.path.basename(folder), os.path.relpath(os.path.join(base, name), folder)))
    print('zip: %s (%.1f MB)' % (zpath, os.path.getsize(zpath) / 1e6))


def build_loader(local=False):
    """Build the player app separately: no models, image libraries, authoring UI or GPU runtime."""
    work = Path(KIT) / 'build'
    parent = work / 'local' if local else Path(KIT) / 'release'
    rel = parent / (LOADER if local else '%s v%s' % (LOADER, VERSION))
    if (not parent.resolve().is_relative_to(Path(KIT).resolve()) or rel.is_symlink()
            or rel.is_junction() or rel.resolve().parent != parent.resolve()):
        raise OSError('Loader output leaves its intended folder.')
    if local:
        local_target(LOADER)
    if rel.is_dir():
        shutil.rmtree(rel)
    excluded = ('numpy', 'PIL', 'moderngl', 'glcontext', 'kit', 'automap', 'objlib', 'viewer',
                'convert', 'render', 'ts3model', 'fbxlib', 'explorer', 'texpack', 'gltf', 'gltflib', 'identity', 'identityfit', 'meshpack', 'meshcli', 'meshtopo', 'audiobank', 'audio_worker')
    for name, entry, windowed in ((LOADER, 'loader.py', True), (LOADER_CLI, 'loadercli.py', False)):
        command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--name', name,
                   '--windowed' if windowed else '--console', '--onedir' if windowed else '--onefile',
                   '--paths', str(Path(KIT) / 'kit'), '--paths', paths.TOOLS,
                   '--distpath', str(work / 'dist'), '--workpath', str(work / 'work'), '--specpath', str(work)]
        for module in excluded + (() if windowed else ('tkinter',)):
            command += ['--exclude-module', module]
        subprocess.run(command + [str(Path(KIT) / 'kit' / entry)], check=True)
    shutil.copytree(work / 'dist' / LOADER, rel)
    shutil.copy2(work / 'dist' / (LOADER_CLI + '.exe'), rel)
    (rel / 'kit').mkdir(); (rel / 'tools').mkdir(); (rel / 'docs').mkdir(); (rel / 'licenses').mkdir()
    for name in ('about', 'paths', 'gamepaths', 'loaderprefs', 'loader', 'loaderui', 'loadercli',
                 'modfile', 'modstore', 'modlayers', 'modpriorityui', 'modview', 'modcli', 'modupdate', 'dropfiles'):
        shutil.copy2(Path(KIT) / 'kit' / (name + '.py'), rel / 'kit')
    shutil.copy2(Path(paths.TOOLS) / 'install.py', rel / 'tools')
    for name in ('LICENSE', 'NOTICE.md'):
        shutil.copy2(Path(KIT) / name, rel)
    shutil.copy2(Path(KIT) / 'docs/LOADER.md', rel / 'README.txt')
    shutil.copy2(Path(KIT) / 'docs/LOADER_AGENTS.md', rel / 'AGENTS.md')
    shutil.copy2(Path(KIT) / 'docs/MOD_FORMAT.md', rel / 'docs')
    shutil.copy2(Path(sys.base_prefix) / 'LICENSE.txt', rel / 'licenses/Python.txt')
    for license_file in glob.glob(os.path.join(sys.base_prefix, 'tcl', 't*8.*', 'license.terms')):
        shutil.copy2(license_file, rel / 'licenses' / ('Tcl-Tk - %s.txt' % Path(license_file).parent.name))
    print('player build: %s' % rel)
    return str(rel)


def main(local=False):
    work = os.path.join(KIT, 'build')
    rel = os.path.join(work, 'local', TOOL) if local else os.path.join(KIT, 'release', '%s v%s' % (TOOL, VERSION))
    # Verify the exact recursive-delete target before cleaning the build output.
    expected = Path(work, 'local').resolve() if local else Path(KIT, 'release').resolve()
    if (not expected.is_relative_to(Path(KIT).resolve()) or Path(rel).is_symlink()
            or Path(rel).is_junction() or Path(rel).resolve().parent != expected):
        raise OSError('Build output leaves its intended folder.')
    if local:
        local_target()
        local_target(LOADER)
    if os.path.isdir(rel):
        shutil.rmtree(rel)
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--windowed', '--name', TOOL,
                    '--paths', os.path.join(KIT, 'kit'), '--paths', paths.TOOLS,
                    '--distpath', os.path.join(work, 'dist'), '--workpath', os.path.join(work, 'work'),
                    '--hidden-import', 'glcontext.wgl', '--hidden-import', 'glcontext.empty',   # moderngl's GL backend
                    '--specpath', work, os.path.join(KIT, 'kit', 'app.py')], check=True)
    shutil.copytree(os.path.join(work, 'dist', TOOL), rel)

    # A separate console executable gives agents real stdout/stderr and reliable exit codes.
    # One-file keeps its bundled runtime separate from the GUI's dependency directory.
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--console', '--onefile', '--name', CLI,
                    '--paths', os.path.join(KIT, 'kit'), '--paths', paths.TOOLS,
                    '--distpath', os.path.join(work, 'dist'), '--workpath', os.path.join(work, 'work'),
                    '--hidden-import', 'glcontext.wgl', '--hidden-import', 'glcontext.empty',
                    '--specpath', work, os.path.join(KIT, 'kit', 'cli.py')], check=True)
    shutil.copy2(os.path.join(work, 'dist', CLI + '.exe'), rel)

    os.makedirs(os.path.join(rel, 'kit', 'pack'))
    for n in KIT_FILES:
        shutil.copy2(os.path.join(KIT, 'kit', n + '.py'), os.path.join(rel, 'kit'))
    for fn in os.listdir(os.path.join(KIT, 'kit', 'pack')):
        shutil.copy2(os.path.join(KIT, 'kit', 'pack', fn), os.path.join(rel, 'kit', 'pack'))
    os.makedirs(os.path.join(rel, 'tools'))
    for n in TOOLS_USED:
        shutil.copy2(os.path.join(paths.TOOLS, n + '.py'), os.path.join(rel, 'tools'))
    shutil.copytree(os.path.join(KIT, 'docs'), os.path.join(rel, 'docs'), ignore=shutil.ignore_patterns('AGENTS.md'))
    shutil.copy2(os.path.join(KIT, 'docs', 'AGENTS.md'), rel)
    shutil.copytree(os.path.join(KIT, 'skill'), os.path.join(rel, 'skill'))
    for fn in ('LICENSE', 'NOTICE.md'):                    # GPL-3.0 + the attribution terms
        shutil.copy2(os.path.join(KIT, fn), rel)
    readme = open(os.path.join(KIT, 'kit', 'README_release.txt'), encoding='utf-8').read().replace('@@VERSION@@', VERSION)
    with open(os.path.join(rel, 'README.txt'), 'w', encoding='utf-8-sig', newline='\r\n') as f:
        f.write(readme)

    # licenses of what the .exe carries inside
    lic = os.path.join(rel, 'licenses')
    os.makedirs(lic)
    shutil.copy2(os.path.join(sys.base_prefix, 'LICENSE.txt'), os.path.join(lic, 'Python.txt'))
    for dist in ('numpy', 'pillow', 'moderngl', 'glcontext'):
        for f in md.distribution(dist).files:
            if 'licen' in f.name.lower() or 'copying' in f.name.lower():
                shutil.copy2(f.locate(), os.path.join(lic, '%s - %s' % (dist, f.name)))
    for p in glob.glob(os.path.join(sys.base_prefix, 'tcl', 't*8.*', 'license.terms')):
        shutil.copy2(p, os.path.join(lic, 'Tcl-Tk - %s.txt' % os.path.basename(os.path.dirname(p))))

    loader_rel = build_loader(local)
    if local:
        to_local(rel)
        to_local(loader_rel, LOADER)
        return
    zpath = rel + '.zip'
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for base, _, files in os.walk(rel):
            for fn in files:
                p = os.path.join(base, fn)
                z.write(p, os.path.join(os.path.basename(rel), os.path.relpath(p, rel)))
    size = sum(os.path.getsize(os.path.join(b, f)) for b, _, fs in os.walk(rel) for f in fs)
    print('release: %s (%.0f MB)\nzip: %s (%.0f MB)' % (rel, size / 1e6, zpath, os.path.getsize(zpath) / 1e6))
    zip_product(loader_rel)


if __name__ == '__main__':
    main(any(arg in ('--local', '--desktop') for arg in sys.argv[1:]))
