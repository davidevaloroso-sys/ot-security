"""Run ONLY in a disposable Linux container with Mosquitto/OpenSSL installed.

Exercises the migration with a real broker and in-memory Kubernetes resources.
It writes /etc/mosquitto and /var/lib/ot-security INSIDE that container.
"""
import base64
import grp
import importlib.util
import json
import os
from pathlib import Path
import pwd
import socket
import ssl
import subprocess
import sys
import time


def main():
    if os.environ.get('OT_DISPOSABLE_MQTT_TEST') != '1' or not Path('/.dockerenv').exists():
        raise SystemExit('This test requires an explicitly enabled disposable Docker container')
    spec = importlib.util.spec_from_file_location('prepare_mqtt_tls',
                                                Path(__file__).resolve().parents[1]/'scripts/prepare_mqtt_tls.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.BROKER = '127.0.0.1'
    (helper.CONFIG/'conf.d').mkdir(exist_ok=True, parents=True)
    for path in (helper.CONFIG/'conf.d').glob('*.conf'):
        raise AssertionError('Unexpected preexisting configuration: ' + str(path))
    main_config = helper.CONFIG/'mosquitto.conf'
    broker_data = Path('/tmp/ot-mqtt-data')
    broker_data.mkdir(mode=0o700)
    broker_account = pwd.getpwnam('mosquitto')
    os.chown(broker_data, broker_account.pw_uid, broker_account.pw_gid)
    main_config.write_text('persistence false\npersistence_location /tmp/ot-mqtt-data/\n'
                           'log_dest stderr\ninclude_dir /etc/mosquitto/conf.d\n')
    original = main_config.read_bytes()
    legacy_config = helper.CONFIG/'conf.d/ot.conf'
    legacy_config.write_text(
        'listener 1883 0.0.0.0\nallow_anonymous false\npassword_file /etc/mosquitto/passwd\n'
        'persistence true\n')
    legacy_original = legacy_config.read_bytes()
    password_file = helper.CONFIG/'passwd'
    password_file.write_text('audit:existing-test-password\n')
    helper.run(['mosquitto_passwd', '-H', 'sha512-pbkdf2', '-U', password_file])
    os.chown(password_file, 0, grp.getgrnam('mosquitto').gr_gid)
    os.chmod(password_file, 0o640)
    previous_passwords = password_file.read_bytes()
    audit = {'data': {key: base64.b64encode(value.encode()).decode() for key, value in
                     [('username', 'audit'), ('password', 'existing-test-password')]}}
    resources = {('secret', 'mqtt-credentials'): audit}
    original_run = helper.run
    process = None
    broker_log = open('/tmp/ot-mqtt-smoke.log', 'w+')

    def restart():
        nonlocal process
        if process is not None:
            process.terminate()
            process.wait(timeout=10)
        process = subprocess.Popen(['mosquitto', '-c', str(main_config)], stdout=broker_log, stderr=broker_log)
        for _ in range(50):
            assert process.poll() is None, 'Mosquitto failed; inspect the test container broker log'
            try:
                with socket.create_connection(('127.0.0.1', 1883), timeout=1):
                    return
            except OSError:
                time.sleep(0.1)
        raise AssertionError('Legacy listener not ready')

    def run(command, data=None):
        if command[0] == 'systemctl':
            if 'restart' in command:
                restart()
            else:
                assert process.poll() is None
            return ''
        return original_run(command, data)

    def kubectl(*args, data=None):
        if args[0] == 'get':
            resource = resources.get((args[1], args[2]))
            return json.dumps(resource) if resource else ''
        assert args == ('create', '-f', '-')
        resource = json.loads(data)
        key = resource['kind'].lower(), resource['metadata']['name']
        assert key not in resources, 'Attempted credential overwrite'
        resources[key] = resource
        return ''

    try:
        restart()
        helper.run = run
        helper.kubectl = kubectl
        original_which = helper.shutil.which
        helper.shutil.which = lambda name: '/test/' + name if name in ('k3s', 'systemctl') else original_which(name)
        sys.argv = ['prepare_mqtt_tls.py']
        helper.main()
        assert not helper.STATE.exists() and not helper.TLS.exists()
        sys.argv.append('--apply')
        helper.main()
        assert resources[('secret', 'mqtt-credentials')] == audit
        assert len(resources) == 5
        assert password_file.read_bytes() == previous_passwords
        assert legacy_config.read_bytes() == legacy_original
        assert (broker_data/'mosquitto.db').is_file(), 'Existing persistence must survive migration'
        assert main_config.read_bytes() == b'per_listener_settings true\n' + original
        assert helper.STATE.stat().st_mode & 0o777 == 0o700
        assert (helper.STATE/'ca.key').stat().st_mode & 0o777 == 0o600
        assert (helper.STATE/'credentials.json').stat().st_mode & 0o777 == 0o600
        assert helper.TLS.stat().st_mode & 0o777 == 0o710
        assert (helper.TLS/'server.key').stat().st_mode & 0o777 == 0o640
        assert not (helper.TLS/'ca.key').exists()
        assert resources[('configmap', 'mqtt-ca')]['data']['ca.crt'] == (helper.TLS/'ca.crt').read_text()
        context = ssl.create_default_context(cafile=str(helper.TLS/'ca.crt'))
        try:
            helper.check_login(context, {'username': 'audit', 'password': 'incorrect-test-password'}, 8883)
        except helper.SetupError:
            pass
        else:
            raise AssertionError('Incorrect password accepted')
        try:
            with socket.create_connection(('127.0.0.1', 8883), timeout=5) as connection:
                context.wrap_socket(connection, server_hostname='192.0.2.1')
        except ssl.SSLCertVerificationError:
            pass
        else:
            raise AssertionError('Incorrect IP SAN accepted')
        try:
            helper.main()
        except helper.SetupError:
            pass
        else:
            raise AssertionError('Rerun should preserve existing credentials and stop')
        print('MQTT migration smoke passed: real TLS, four logins, original 1883 account, invalid password/IP, '
              'private file modes, create-only resources and rerun protection.')
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        broker_log.close()


if __name__ == '__main__':
    main()
