"""One-time migration of the observed Ubuntu Mosquitto listener; run locally as root.

Default: read-only checks. --apply adds TLS alongside the existing 1883 listener,
then creates only the three missing MQTT Secrets and the public CA ConfigMap.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import ssl
import struct
import subprocess
import sys
import time

BROKER = '192.168.1.21'
NAMESPACE = 'ot-namespace'
ROLES = {'mqtt-raspi-simulator': 'ot-simulator-tls',
         'mqtt-ia-consumer': 'ot-ia-tls', 'mqtt-nodered': 'ot-nodered-tls'}
STATE = Path('/var/lib/ot-security/mqtt-bootstrap')
CONFIG = Path('/etc/mosquitto')
TLS = CONFIG / 'ot-security-tls'
EXTRA = CONFIG / 'conf.d/ot-tls.conf'


class SetupError(RuntimeError):
    """A diagnostic that contains no credential values."""


def run(command, data=None):
    try:
        result = subprocess.run([str(part) for part in command], input=data,
                                text=True, capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        raise SetupError(f'Cannot complete {command[0]}; raw output withheld') from None
    if result.returncode:
        raise SetupError(f'{command[0]} failed; raw output withheld')
    return result.stdout


def kubectl(*args, data=None):
    return run(['k3s', 'kubectl', '--request-timeout=30s', '-n', NAMESPACE, *args], data)


def read_resource(kind, name):
    result = kubectl('get', kind, name, '--ignore-not-found', '-o', 'json')
    return json.loads(result) if result.strip() else None


def directives(text):
    return [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')]


def check_layout(directory):
    """Fail closed for layouts different from the one inspected on this VM."""
    main = directory / 'mosquitto.conf'
    legacy = directory / 'conf.d/ot.conf'
    if main.is_symlink() or legacy.is_symlink():
        raise SetupError('Review symlinked Mosquitto configuration before migrating')
    expected = ['listener 1883 0.0.0.0', 'allow_anonymous false',
                'password_file /etc/mosquitto/passwd']
    legacy_options = directives(legacy.read_text())
    persistence = [line for line in legacy_options if line.split()[0] == 'persistence']
    # Global boolean observed in ot.conf. Preserve the file and its position:
    # moving this option could change precedence relative to mosquitto.conf.
    if len(persistence) > 1 or any(line.split() not in (
            ['persistence', 'true'], ['persistence', 'false']) for line in persistence):
        raise SetupError('Legacy ot.conf requires a single valid persistence boolean; values withheld')
    security_options = [line for line in legacy_options if line.split()[0] != 'persistence']
    if security_options != expected:
        raise SetupError('Legacy ot.conf has unexpected listener/authentication settings; review before migrating')
    allowed = {'pid_file', 'persistence', 'persistence_location', 'log_dest',
               'log_type', 'connection_messages', 'include_dir'}
    options = directives(main.read_text())
    if any(line.split()[0] not in allowed for line in options):
        raise SetupError('Main configuration has additional settings; review before migrating')
    if [line for line in options if line.startswith('include_dir ')] != ['include_dir /etc/mosquitto/conf.d']:
        raise SetupError('Unexpected Mosquitto include directories')
    for path in (directory / 'conf.d').glob('*.conf'):
        if path != legacy and directives(path.read_text()):
            raise SetupError('Additional Mosquitto listener configuration requires review')
    return main.read_bytes()


def accounts(audit):
    try:
        original = {key: base64.b64decode(audit['data'][key], validate=True).decode('utf-8')
                    for key in ('username', 'password')}
    except (KeyError, TypeError, ValueError, UnicodeError):
        raise SetupError('Existing mqtt-credentials must contain valid username/password') from None
    if (not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', original['username'])
            or original['username'] in ROLES.values()
            or not original['password'] or any(c in original['password'] for c in '\r\n\x00')):
        raise SetupError('Existing audit account needs manual review; values withheld')
    return {'mqtt-credentials': original, **{
        name: {'username': user, 'password': secrets.token_urlsafe(32)} for name, user in ROLES.items()}}


def acl(users):
    topics = ['lab/raspi1/temperature', 'lab/raspi1/humidity']
    lines = [f'user {users["mqtt-credentials"]["username"]}', 'topic read lab/#']
    for role, permissions in (
        ('mqtt-raspi-simulator', [('write', topic) for topic in topics]),
        ('mqtt-ia-consumer', [('read', topic) for topic in topics] + [('write', 'lab/raspi1/anomaly')]),
        ('mqtt-nodered', [('read', topic) for topic in topics + ['lab/raspi1/anomaly']]),
    ):
        lines.append('user ' + users[role]['username'])
        lines.extend(f'topic {action} {topic}' for action, topic in permissions)
    return '\n'.join(lines) + '\n'


def private_file(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(data)


def create_certificates(state, destination):
    run(['openssl', 'req', '-x509', '-newkey', 'rsa:3072', '-nodes', '-sha256',
         '-days', '3650', '-subj', '/CN=OT Lab MQTT CA', '-keyout', state / 'ca.key',
         '-out', destination / 'ca.crt', '-addext', 'basicConstraints=critical,CA:TRUE',
         '-addext', 'keyUsage=critical,keyCertSign,cRLSign'])
    run(['openssl', 'req', '-new', '-newkey', 'rsa:3072', '-nodes', '-sha256',
         '-subj', '/CN=OT Lab MQTT', '-keyout', destination / 'server.key', '-out', state / 'server.csr'])
    extensions = state / 'server.ext'
    private_file(extensions, 'basicConstraints=critical,CA:FALSE\n'
                 'keyUsage=critical,digitalSignature,keyEncipherment\n'
                 'extendedKeyUsage=serverAuth\nsubjectAltName=IP:' + BROKER + '\n')
    run(['openssl', 'x509', '-req', '-in', state / 'server.csr', '-CA', destination / 'ca.crt',
         '-CAkey', state / 'ca.key', '-set_serial', str(secrets.randbits(128) or 1),
         '-days', '825', '-sha256', '-extfile', extensions, '-out', destination / 'server.crt'])
    run(['openssl', 'verify', '-CAfile', destination / 'ca.crt',
         '-verify_ip', BROKER, destination / 'server.crt'])


def tls_config(directory):
    return ('listener 8883 0.0.0.0\nallow_anonymous false\n'
            + ''.join(f'{option} {directory / filename}\n' for option, filename in (
                ('password_file', 'passwd'), ('acl_file', 'acl'),
                ('certfile', 'server.crt'), ('keyfile', 'server.key')))
            + 'tls_version tlsv1.2\n')


def check_login(context, user, port):
    """MQTT CONNECT/DISCONNECT only: no publication or persistent subscription."""
    def field(value):
        raw = value.encode('utf-8')
        return struct.pack('!H', len(raw)) + raw
    payload = (field('MQTT') + bytes([4, 0xc2, 0, 15])
               + field('ot-migration-' + secrets.token_hex(8))
               + field(user['username']) + field(user['password']))
    length = len(payload)
    remaining = bytearray()
    while True:
        digit = length % 128
        length //= 128
        remaining.append(digit | (0x80 if length else 0))
        if not length:
            break
    with socket.create_connection((BROKER, port), timeout=5) as plain:
        connection = context.wrap_socket(plain, server_hostname=BROKER) if context else plain
        with connection:
            connection.sendall(b'\x10' + remaining + payload)
            reply = b''
            while len(reply) < 4:
                chunk = connection.recv(4 - len(reply))
                if not chunk:
                    break
                reply += chunk
            if reply != b'\x20\x02\x00\x00':
                raise SetupError(f'MQTT authentication failed on port {port}; values withheld')
            connection.sendall(b'\xe0\x00')


def activate(main, original, extra, users, ca, group):
    if main.read_bytes() != original:
        raise SetupError('Mosquitto configuration changed during preparation; activation aborted')
    created = False
    changed = False
    try:
        private_file(extra, tls_config(ca.parent))
        created = True
        os.chown(extra, 0, group)
        os.chmod(extra, 0o640)
        changed = True
        main.write_bytes(b'per_listener_settings true\n' + original)
        run(['systemctl', 'restart', 'mosquitto'])
        context = ssl.create_default_context(cafile=str(ca))
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        for attempt in range(10):
            try:
                for user in users.values():
                    check_login(context, user, 8883)
                check_login(None, users['mqtt-credentials'], 1883)
                return
            except OSError:
                if attempt == 9:
                    raise
                time.sleep(1)
    except (OSError, SetupError, KeyboardInterrupt):
        if changed:
            main.write_bytes(original)
        if created:
            extra.unlink()
        if changed:
            run(['systemctl', 'restart', 'mosquitto'])
        raise SetupError('TLS activation failed; original broker configuration restored. '
                         'Protected generated files were retained for investigation') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not sys.platform.startswith('linux') or os.geteuid() != 0:
        raise SetupError('Run this script with sudo on the Ubuntu K3s VM')
    os.umask(0o077)
    for command in ('k3s', 'openssl', 'mosquitto_passwd', 'systemctl'):
        if not shutil.which(command):
            raise SetupError('Required command not installed: ' + command)
    original = check_layout(CONFIG)
    if any(path.exists() or path.is_symlink() for path in (STATE, TLS, EXTRA)):
        raise SetupError('Migration files already exist; refusing to overwrite or rotate them')
    run(['systemctl', 'is-active', '--quiet', 'mosquitto'])
    users = accounts(read_resource('secret', 'mqtt-credentials'))
    for kind, names in [('secret', ROLES), ('configmap', ['mqtt-ca'])]:
        for name in names:
            if read_resource(kind, name) is not None:
                raise SetupError(f'{kind} {name} already exists; refusing to overwrite')
    check_login(None, users['mqtt-credentials'], 1883)
    print('Legacy configuration, audit login and absent target resources verified.')
    if not args.apply:
        print('Read-only check complete. --apply adds 8883 and briefly restarts Mosquitto; 1883 remains enabled.')
        return
    import grp  # Ubuntu-only; keep pure helpers testable on Windows.
    group = grp.getgrnam('mosquitto').gr_gid
    STATE.mkdir(mode=0o700, parents=True)
    TLS.mkdir(mode=0o750)
    os.chown(TLS, 0, group)
    # Directory traversal for the broker group, with no group write or other access.
    os.chmod(TLS, 0o710)  # nosec B103
    private_file(STATE / 'mosquitto.conf.before', original.decode())
    private_file(STATE / 'credentials.json', json.dumps(users))
    create_certificates(STATE, TLS)
    private_file(TLS / 'passwd', ''.join(f'{u["username"]}:{u["password"]}\n' for u in users.values()))
    # Convert only this NEW plaintext file, never /etc/mosquitto/passwd.
    run(['mosquitto_passwd', '-H', 'sha512-pbkdf2', '-U', TLS / 'passwd'])
    private_file(TLS / 'acl', acl(users))
    for path in TLS.iterdir():
        os.chown(path, 0, group)
        os.chmod(path, 0o640)
    print('Certificates and separate TLS accounts prepared. Restarting Mosquitto with rollback on failure.')
    activate(CONFIG / 'mosquitto.conf', original, EXTRA, users, TLS / 'ca.crt', group)
    print('TLS/IP SAN and four account logins verified; legacy audit login still works on 1883.')
    # Broker is validated before credentials are installed. Never replace an existing resource.
    for name in ROLES:
        resource = {'apiVersion': 'v1', 'kind': 'Secret', 'type': 'Opaque',
                    'metadata': {'name': name, 'namespace': NAMESPACE}, 'stringData': users[name]}
        kubectl('create', '-f', '-', data=json.dumps(resource))
        print('Created Secret ' + name)
    resource = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'mqtt-ca', 'namespace': NAMESPACE},
                'data': {'ca.crt': (TLS / 'ca.crt').read_text()}}
    kubectl('create', '-f', '-', data=json.dumps(resource))
    print('Created ConfigMap mqtt-ca. Protected backup/credentials: ' + str(STATE))
    print('Next: prepare nodered-auth and grafana-influxdb against the existing InfluxDB. No workloads were deployed.')


if __name__ == '__main__':
    try:
        main()
    except SetupError as error:
        sys.exit(str(error))
    except (OSError, ValueError, KeyError, TypeError):
        sys.exit('Preparation failed; raw output withheld. Preserve generated files and inspect the last completed step.')
