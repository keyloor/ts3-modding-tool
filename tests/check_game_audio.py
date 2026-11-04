"""Opt-in exhaustive FMOD regression; reads the selected game, writes only a new report directory.

python -I tests/check_game_audio.py --game GAME --out NEW_REPORT_DIRECTORY
Does not play audio or install anything. No game data is checked into the repository.
"""
import argparse
import concurrent.futures as futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'kit'))
import audiobank as A
from explorer import Browser
from modfile import ModError, inside


def check_bank(game, path, seconds):
    from audio_worker import Decoder
    browser = Browser(game)
    source = browser.source(path); raw = browser.read(path)
    before = hashlib.sha256(raw).hexdigest()
    parsed = A.bank(raw); failed = []; count = len(parsed['sounds']); fingerprint = hashlib.sha256()
    with tempfile.TemporaryDirectory(prefix='ts3-audio-audit-') as temp:
        fsb, wav = Path(temp)/'input.fsb', Path(temp)/'output.wav'; fsb.write_bytes(parsed['fsb'])
        del raw
        with Decoder(inside(browser.game, 'fmod.dll'), fsb) as decoder:
            for track, sample in enumerate(parsed['sounds']):
                try:
                    decoder.decode(wav, track, seconds)
                    if wav.stat().st_size > A.MAX_PCM: raise ValueError('Decoded size limit exceeded.')
                    result = wav.read_bytes(); A.validate_wav(result, sample, seconds)
                    fingerprint.update(hashlib.sha256(result).digest())
                except Exception as e:
                    failed.append(dict(track=track, name=sample['name'], problem=str(e), details=getattr(e, 'details', {})))
                if (track+1) % 512 == 0:
                    print(json.dumps(dict(progress=track+1, total=count)), flush=True)
    unchanged = hashlib.sha256(source.read_bytes()).hexdigest() == before
    return dict(path=path, samples=count, passed=count-len(failed), failed=failed,
                unchanged=unchanged, source_sha256=before, decoded_sha256=fingerprint.hexdigest())


def worker(game, path, seconds, log):
    command = [sys.executable, '-I', str(Path(__file__).resolve()), '--worker', str(game), path, str(seconds)]
    # Native failures remain isolated to one bank. A timeout is a failed bank, never silently skipped.
    with log.open('w', encoding='utf-8') as output:
        try:
            process = subprocess.Popen(command, stdout=output, stderr=output,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            with process:
                try: code = process.wait(timeout=600)
                finally:
                    if process.poll() is None: process.kill(); process.wait()
        except subprocess.TimeoutExpired:
            return dict(path=path, fatal='Bank decoder timed out.')
    lines = log.read_text(encoding='utf-8', errors='replace').splitlines()
    try: result = json.loads(lines[-1])
    except (ValueError, IndexError): result = dict(path=path, fatal='Native worker failed.', exit_code=code)
    if code and not result.get('fatal'): result = dict(path=path, fatal='Native worker failed.', exit_code=code)
    return result


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--worker':
        try: print(json.dumps(check_bank(sys.argv[2], sys.argv[3], float(sys.argv[4]))), flush=True)
        except Exception as e: print(json.dumps(dict(path=sys.argv[3], fatal=str(e))), flush=True); return 1
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', required=True)
    parser.add_argument('--out', required=True, help='new directory outside the game')
    parser.add_argument('--seconds', type=float, default=120, help='maximum excerpt per sample, default 120 seconds')
    parser.add_argument('--jobs', type=int, choices=(1, 2, 3, 4), default=2)
    args = parser.parse_args(); A.options(0, args.seconds)
    browser = Browser(args.game); out = Path(args.out).absolute()
    if out.exists() or out.is_symlink() or out.resolve().is_relative_to(browser.game): parser.error('Choose a new output directory outside the game.')
    out.mkdir(parents=True); (out/'logs').mkdir()
    paths, skipped = [], []
    for base in ('assets', 'data_dx'):
        for folder, dirs, files in os.walk(inside(browser.game, base)):
            dirs[:] = [d for d in dirs if not Browser._linked(Path(folder)/d)]
            for name in files:
                if Path(name).suffix.lower() not in ('.bank', '.fsb'): continue
                file = Path(folder)/name; path = file.relative_to(browser.game).as_posix()
                try: A.bank(browser.read(path))
                except ModError as e:
                    if e.code != 'no_audio': raise
                    skipped.append(dict(path=path, sha256=hashlib.sha256(file.read_bytes()).hexdigest())); continue
                paths.append(path)
    print('Checking %d audio banks, %d event/metadata banks without samples.' % (len(paths), len(skipped)), flush=True)
    started, results = time.monotonic(), []
    with futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        pending = {pool.submit(worker, browser.game, path, args.seconds, out/'logs'/('%03d.jsonl' % i)): path
                   for i, path in enumerate(sorted(paths))}
        while pending:
            done, _ = futures.wait(pending, timeout=10, return_when=futures.FIRST_COMPLETED)
            for job in done:
                path = pending.pop(job); result = job.result(); results.append(result)
                print('%d/%d banks: %s; %d passed, %d failed%s' % (len(results), len(paths), path,
                      result.get('passed', 0), len(result.get('failed', [])), '; '+result['fatal'] if result.get('fatal') else ''), flush=True)
            if not done:
                print('%d/%d banks complete; %.0f seconds elapsed.' % (len(results), len(paths), time.monotonic()-started), flush=True)
    skips_unchanged = all(hashlib.sha256(browser.source(row['path']).read_bytes()).hexdigest() == row['sha256'] for row in skipped)
    report = dict(schema_version=1, seconds=args.seconds, banks=sorted(results, key=lambda r:r['path']), skipped=skipped,
                  passed=sum(r.get('passed', 0) for r in results), failed=sum(len(r.get('failed', [])) for r in results),
                  fatal=sum(bool(r.get('fatal')) for r in results),
                  unchanged=skips_unchanged and all(r.get('unchanged', False) for r in results), elapsed_seconds=time.monotonic()-started)
    (out/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('banks', 'skipped')}), flush=True)
    return 0 if not report['failed'] and not report['fatal'] and report['unchanged'] else 1


if __name__ == '__main__': raise SystemExit(main())
