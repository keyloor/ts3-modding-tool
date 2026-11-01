"""Build the kit's release: release/TS3 Modding Tool v<version>/ and its zip.

  python build_kit.py              the release folder + zip
  python build_kit.py --desktop    the same folder on the Desktop (no zip) + a shortcut to the .exe: the user's
                                   always-current copy, rebuilt after every change

'Toy Story 3 Modding Tool.exe' (PyInstaller, one folder, no console) + the kit's and the tools' Python source (for the
command line and AI agents), docs, the skill, the license, and the licenses of what the .exe carries inside
(Python, numpy, Pillow, moderngl, glcontext, Tcl/Tk).
"""
import glob, importlib.metadata as md, os, shutil, subprocess, sys, zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
from about import TOOL, VERSION

KIT = paths.KIT
TOOLS_USED = ['octlib', 'fbxlib', 'ts3model', 'convert', 'render', 'install', 'build_release', 'zx', 'zls', 'rt',
              'fbxinfo', 'bones5', 'dump', 'texpeek', 'angles', 'skelcmp', 'fmodbank']
KIT_FILES = ['about', 'paths', 'automap', 'autotex', 'objlib', 'viewer', 'modfile', 'modstore', 'modupdate', 'dropfiles',
             'modcli', 'cli', 'kit', 'app', 'build_kit', 'explorer', 'explorercli', 'explorerui']
CLI = 'TS3 Modding CLI'
SHORTCUT = 'Abrir ' + TOOL + '.lnk'


def desktop():
    import ctypes
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf)      # CSIDL_DESKTOPDIRECTORY (OneDrive too)
    return buf.value


def exe_running(folder):
    """is the .exe of that folder open? (its files can't be replaced then)"""
    exes = {os.path.join(folder, name + '.exe').lower() for name in (TOOL, CLI)}
    out = subprocess.run(['powershell', '-NoProfile', '-Command',
                          "Get-Process | Where-Object { $_.Path } | ForEach-Object { $_.Path }"],
                         capture_output=True, text=True).stdout.lower()
    return bool(exes.intersection(out.splitlines()))


def to_desktop(rel):
    """replace <Desktop>/<TOOL> with the new build, and point the shortcut at its .exe"""
    dst = os.path.join(desktop(), TOOL)
    if exe_running(dst):
        sys.exit('%s is open from the Desktop: close it and run this again' % TOOL)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(rel, dst)
    lnk = os.path.join(desktop(), SHORTCUT)
    ps = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%s'); $s.TargetPath = '%s'; "
          "$s.WorkingDirectory = '%s'; $s.Description = '%s'; $s.Save()") % (
        lnk.replace("'", "''"), os.path.join(dst, TOOL + '.exe').replace("'", "''"), dst.replace("'", "''"), TOOL)
    subprocess.run(['powershell', '-NoProfile', '-Command', ps], check=True)
    print('desktop: %s\nshortcut: %s' % (dst, lnk))


def main(to_desk=False):
    work = os.path.join(KIT, 'build')
    rel = os.path.join(work, 'desktop', TOOL) if to_desk else os.path.join(KIT, 'release', '%s v%s' % (TOOL, VERSION))
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

    if to_desk:
        to_desktop(rel)
        return
    zpath = rel + '.zip'
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for base, _, files in os.walk(rel):
            for fn in files:
                p = os.path.join(base, fn)
                z.write(p, os.path.join(os.path.basename(rel), os.path.relpath(p, rel)))
    size = sum(os.path.getsize(os.path.join(b, f)) for b, _, fs in os.walk(rel) for f in fs)
    print('release: %s (%.0f MB)\nzip: %s (%.0f MB)' % (rel, size / 1e6, zpath, os.path.getsize(zpath) / 1e6))


if __name__ == '__main__':
    main('--desktop' in sys.argv[1:])
