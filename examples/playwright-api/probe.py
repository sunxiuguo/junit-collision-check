"""Generate real Playwright JUnit and audit its identities using synthetic HTTP."""
from __future__ import annotations

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from urllib.parse import parse_qs, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent


class Handler(BaseHTTPRequestHandler):
    calls: list[dict] = []

    def do_GET(self):
        url = urlsplit(self.path)
        status = 200
        if url.path.startswith('/catalog/'):
            payload = {'id': url.path.rsplit('/', 1)[-1], 'synthetic': True}
        elif url.path == '/transient':
            status = 200 if parse_qs(url.query).get('attempt') == ['1'] else 503
            payload = {'synthetic': True}
        elif url.path == '/always-fails':
            status, payload = 503, {'synthetic': True}
        else:
            status, payload = 404, {'synthetic': True}
        self.calls.append({'path': self.path, 'status': status})
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def run(command, env, log):
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=90)
    log.write_text(result.stdout + result.stderr)
    return result.returncode


def require(condition: bool, detail: str) -> None:
    """Keep acceptance checks enabled even when Python assertions are stripped."""
    if not condition:
        raise RuntimeError(detail)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--auditor-python', required=True)
    args = parser.parse_args()
    out = ROOT / 'artifacts'
    out.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_env = {key: os.environ[key] for key in ('PATH', 'SystemRoot', 'WINDIR', 'COMSPEC', 'TEMP', 'TMP', 'TMPDIR') if key in os.environ}
    base_env.update({'LANG': 'C.UTF-8', 'NO_COLOR': '1', 'PYTHONNOUSERSITE': '1', 'SYNTHETIC_BASE_URL': f'http://127.0.0.1:{server.server_port}'})
    summaries = []
    cli = ['node', str(ROOT / 'node_modules/@playwright/test/cli.js'), 'test', '--config', str(ROOT / 'playwright.config.mjs')]
    scenarios = [
        ('default', 'normal', '0', [], 0),
        ('prefixed', 'normal', '1', [], 0),
        ('retry', 'retry', '1', [], 0),
        ('final-failure', 'final-failure', '1', ['--project=api-one'], 1),
        ('shard-1', 'normal', '1', ['--shard=1/2'], 0),
        ('shard-2', 'normal', '1', ['--shard=2/2'], 0),
    ]
    try:
        for name, case, prefix, extra, expected_exit in scenarios:
            report = out / f'{name}.xml'
            with tempfile.TemporaryDirectory(prefix='junit-playwright-') as temporary:
                fresh_report = Path(temporary) / 'report.xml'
                env = {**base_env, 'CASE': case, 'PREFIX': prefix, 'REPORT': str(fresh_report)}
                code = run(cli + extra, env, out / f'{name}.log')
                require(code == expected_exit, f"{name}: expected runner exit {expected_exit}, got {code}")
                report.write_bytes(fresh_report.read_bytes())
            tree = ET.parse(report)
            cases = tree.findall('.//testcase')
            keys = [(c.attrib['classname'], c.attrib['name']) for c in cases]
            summaries.append({'scenario': name, 'runner_exit': code, 'records': len(cases), 'unique_identity_count': len(set(keys)), 'retry_metadata_count': sum(len(c.findall('flakyFailure')) + len(c.findall('flakyError')) + len(c.findall('rerunFailure')) + len(c.findall('rerunError')) for c in cases), 'failed_records': sum(c.find('failure') is not None or c.find('error') is not None for c in cases), 'sha256': hashlib.sha256(report.read_bytes()).hexdigest()})
        for name, files, expected_exit in [
            ('default', ['default.xml'], 1),
            ('prefixed', ['prefixed.xml'], 0),
            ('retry', ['retry.xml'], 0),
            ('final-failure', ['final-failure.xml'], 0),
            ('shards', ['shard-1.xml', 'shard-2.xml'], 0),
            ('overlap-control', ['prefixed.xml', 'shard-1.xml', 'shard-2.xml'], 1),
        ]:
            command = [args.auditor_python, '-m', 'junit_collision_check', '--format=json', *[str(out / f) for f in files]]
            before = {file: hashlib.sha256((out / file).read_bytes()).hexdigest() for file in files}
            result = subprocess.run(command, cwd=ROOT, env=base_env, capture_output=True, text=True, timeout=30)
            require(result.returncode == expected_exit, f"{name}: expected auditor exit {expected_exit}, got {result.returncode}: {result.stdout}{result.stderr}")
            require(before == {file: hashlib.sha256((out / file).read_bytes()).hexdigest() for file in files}, f"{name}: auditor changed input XML")
            audit = json.loads(result.stdout)
            expected = {
                'default': (4, 2, 2, 2, 0),
                'prefixed': (4, 4, 0, 0, 0),
                'retry': (2, 2, 0, 0, 2),
                'final-failure': (1, 1, 0, 0, 0),
                'shards': (4, 4, 0, 0, 0),
                'overlap-control': (8, 4, 4, 4, 0),
            }[name]
            fields = ('testcases', 'unique_identities', 'duplicate_records', 'collision_groups', 'cases_with_retry_metadata')
            require(tuple(audit['summary'][key] for key in fields) == expected, f"{name}: unexpected audit counts: {audit}")
            require(audit['diagnostics'] == [] and audit['summary']['potential_hidden_failure_groups'] == 0, f"{name}: unexpected diagnostics or hidden failures: {audit}")
            (out / f'audit-{name}.json').write_text(result.stdout)
            summaries.append({'audit': name, 'exit': result.returncode, 'inputs': files, 'result': audit})
        retry = next(x for x in summaries if x.get('scenario') == 'retry')
        require(retry['records'] == 2 and retry['retry_metadata_count'] == 2 and retry['failed_records'] == 0, f"retry: unexpected metadata or outcomes: {retry}")
        failure = next(x for x in summaries if x.get('scenario') == 'final-failure')
        require(failure['records'] == 1 and failure['failed_records'] == 1, f"final-failure: unexpected outcomes: {failure}")
        require(len(Handler.calls) == 17, f"expected 17 HTTP requests, got {len(Handler.calls)}: {Handler.calls}")
        (out / 'http-calls.json').write_text(json.dumps(Handler.calls, indent=2) + '\n')
        (out / 'results.json').write_text(json.dumps({'producer': '@playwright/test 1.64.1', 'consumer': 'junit-collision-check 0.2.0a1', 'synthetic_http_requests': len(Handler.calls), 'browser_launched': False, 'scenarios': summaries}, indent=2) + '\n')
        print(json.dumps({'scenario_count': len(scenarios), 'audit_count': 6, 'synthetic_http_requests': len(Handler.calls), 'result': 'passed'}))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == '__main__':
    main()
