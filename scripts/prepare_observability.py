"""Create missing observability Secrets against the existing DB; never replace them."""
import argparse
import base64
from contextlib import contextmanager
import json
import secrets
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode

from provision_influx_tokens import api

NAMESPACE = 'ot-namespace'
BASE = 'http://127.0.0.1:18086'
REQUIRED = {
    'grafana-influxdb': ('INFLUXDB_READ_TOKEN',),
    'nodered-auth': ('NODE_RED_ADMIN_USER', 'NODE_RED_ADMIN_PASSWORD_HASH',
                     'NODE_RED_CREDENTIAL_SECRET', 'INFLUXDB_WRITE_TOKEN'),
}


class PreparationError(RuntimeError):
    """Sanitized diagnostics only."""


def kubectl(*args, data=None):
    result = subprocess.run(['kubectl', '--request-timeout=30s', '-n', NAMESPACE, *args],
                            input=data, text=True, capture_output=True, timeout=60, check=False)
    if result.returncode:
        for marker in ('Explicit credentialSecret requires review',
                       'Existing credentials require encryption key review',
                       'Invalid old encryption key'):
            if marker in result.stderr:
                raise PreparationError(marker + '; existing Node-RED files untouched')
        raise PreparationError('Kubernetes operation failed; raw output withheld. Existing Secrets preserved.')
    return result.stdout


def read_secret(name):
    raw = kubectl('get', 'secret', name, '--ignore-not-found', '-o', 'json')
    if not raw.strip():
        return None
    return {key: base64.b64decode(value, validate=True).decode('utf-8')
            for key, value in json.loads(raw).get('data', {}).items()}


def require_fields(data, fields, resource):
    missing = [key for key in fields if not isinstance(data.get(key), str) or not data[key]]
    if missing:
        raise PreparationError(resource + ' has missing/empty fields: ' + ', '.join(missing))


@contextmanager
def forward():
    # Verify that this process owns the forwarding socket, not an unrelated service.
    with tempfile.TemporaryFile(mode='w+') as log:
        process = subprocess.Popen(['kubectl', '-n', NAMESPACE, 'port-forward',
                                    '--address=127.0.0.1', 'service/influxdb', '18086:8086'],
                                   stdout=log, stderr=log, text=True)
        try:
            for _ in range(100):
                if process.poll() is not None:
                    raise PreparationError('InfluxDB port-forward failed; raw output withheld')
                log.seek(0)
                if 'Forwarding from 127.0.0.1:18086' in log.read():
                    break
                time.sleep(0.1)
            else:
                raise PreparationError('InfluxDB port-forward did not become ready')
            yield
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)


def bucket_identity(admin):
    token = admin['INFLUXDB_ADMIN_TOKEN']
    if api(BASE, token, '/api/v2/setup').get('allowed') is not False:
        raise PreparationError('Existing initialized InfluxDB required; no setup/reset performed')
    organizations = api(BASE, token, '/api/v2/orgs?' + urlencode({'org': admin['INFLUXDB_ORG']}))['orgs']
    if len(organizations) != 1:
        raise PreparationError('Expected exactly one existing InfluxDB organization')
    org = organizations[0]['id']
    buckets = api(BASE, token, '/api/v2/buckets?' + urlencode(
        {'orgID': org, 'name': admin['INFLUXDB_BUCKET']}))['buckets']
    if len(buckets) != 1:
        raise PreparationError('Expected exactly one existing InfluxDB bucket')
    return org, buckets[0]['id']


def scoped_token(admin_token, org, bucket, name, action):
    description = 'ot-security-bootstrap/' + name
    permissions = [{'action': action, 'resource': {'type': 'buckets', 'id': bucket, 'orgID': org}}]
    existing = api(BASE, admin_token, '/api/v2/authorizations?' + urlencode({'orgID': org}))['authorizations']
    matching = [auth for auth in existing if auth.get('description') == description]
    if len(matching) > 1:
        raise PreparationError('Multiple bootstrap authorizations for ' + name + '; review required')
    if matching:
        auth = matching[0]
        actual = auth.get('permissions', [])
        valid = len(actual) == 1 and actual[0].get('action') == action
        resource = actual[0].get('resource', {}) if actual else {}
        valid = valid and resource.get('type') == 'buckets' and resource.get('id') == bucket
        valid = valid and resource.get('orgID') == org and auth.get('orgID') == org
        if not valid or auth.get('status') != 'active':
            raise PreparationError('Existing bootstrap authorization scope/status differs for ' + name)
    else:
        auth = api(BASE, admin_token, '/api/v2/authorizations', {
            'orgID': org, 'description': description, 'permissions': permissions,
        })
    if not isinstance(auth.get('token'), str) or not auth['token']:
        raise PreparationError('Authorization exists but token is unavailable for ' + name
                               + '; recover it before retrying. No automatic rotation.')
    return auth['token']


# Read only existing files. Never evaluate settings.js or rewrite the old flows.
# Refuse custom encryption settings whose meaning cannot be established safely.
NODE_AUTH = r'''
const fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const bcrypt = require(require.resolve('bcryptjs', {paths: ['/usr/src/node-red', '/data']}));
const settings = fs.readFileSync('/data/settings.js', 'utf8');
const active = settings.replace(/\/\*[\s\S]*?\*\//g, '').split('\n')
  .filter(line => !line.trim().startsWith('//')).join('\n');
if (/\bcredentialSecret\s*:/.test(active)) {
  throw new Error('Explicit credentialSecret requires review');
}
const runtimePath = '/data/.config.runtime.json';
const runtime = fs.existsSync(runtimePath) ? JSON.parse(fs.readFileSync(runtimePath, 'utf8')) : {};
const encrypted = fs.readdirSync('/data').filter(name => name.endsWith('_cred.json'))
  .some(name => Object.keys(JSON.parse(fs.readFileSync('/data/' + name, 'utf8'))).length > 0);
let key = runtime._credentialSecret;
if (key !== undefined && (typeof key !== 'string' || !key)) throw new Error('Invalid old encryption key');
if (encrypted && !key) throw new Error('Existing credentials require encryption key review');
process.stdout.write(JSON.stringify({
  NODE_RED_ADMIN_USER: 'ot-admin',
  NODE_RED_ADMIN_PASSWORD: input.password,
  NODE_RED_ADMIN_PASSWORD_HASH: bcrypt.hashSync(input.password, 12),
  NODE_RED_CREDENTIAL_SECRET: key || input.key
}));
'''


def node_auth():
    raw = kubectl('exec', '-i', 'deployment/nodered', '--', 'node', '-e', NODE_AUTH,
                  data=json.dumps({'password': secrets.token_urlsafe(32), 'key': secrets.token_urlsafe(48)}))
    result = json.loads(raw)
    require_fields(result, REQUIRED['nodered-auth'][:-1], 'Node-RED authentication')
    return result


def create_secret(name, data):
    resource = {'apiVersion': 'v1', 'kind': 'Secret', 'type': 'Opaque',
                'metadata': {'name': name, 'namespace': NAMESPACE}, 'stringData': data}
    kubectl('create', '-f', '-', data=json.dumps(resource))
    print('Created Secret ' + name + '; values withheld')


def prepare(apply=False):
    missing = []
    for name, fields in REQUIRED.items():
        existing = read_secret(name)
        if existing is None:
            missing.append(name)
        else:
            require_fields(existing, fields, name)
            print('Preserving existing Secret ' + name)
    if not missing:
        return
    admin = read_secret('observability-secrets') or {}
    require_fields(admin, ('INFLUXDB_ADMIN_TOKEN', 'INFLUXDB_ORG', 'INFLUXDB_BUCKET'), 'observability-secrets')
    # Establish encryption compatibility before issuing any database token.
    auth = node_auth() if 'nodered-auth' in missing else None
    with forward():
        org, bucket = bucket_identity(admin)
        if not apply:
            print('Read-only checks passed; missing Secrets: ' + ', '.join(missing))
            return
        for name in missing:
            action = 'read' if name == 'grafana-influxdb' else 'write'
            token = scoped_token(admin['INFLUXDB_ADMIN_TOKEN'], org, bucket, name, action)
            data = {'INFLUXDB_READ_TOKEN': token} if action == 'read' else {**auth, 'INFLUXDB_WRITE_TOKEN': token}
            create_secret(name, data)
    print('Observability Secrets ready. No database setup, PVC or workload changes performed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        prepare(args.apply)
    except PreparationError as error:
        sys.exit('Observability preparation failed: ' + str(error))
    except Exception:
        sys.exit('Observability preparation failed; raw output withheld. '
                 'Preserve existing Secrets and authorizations; no automatic rotation.')
