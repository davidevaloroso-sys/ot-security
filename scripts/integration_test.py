"""Disposable real-stack test. Requires Docker, OpenSSL and requirements-dev.txt.

Uses generated test credentials and isolated containers; never contacts the lab.
"""
import argparse
import base64
import csv
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import ssl
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import paho.mqtt.client as mqtt
import yaml
from provision_influx_tokens import scoped_tokens
from initialize_influx import initialize

ROOT = Path(__file__).resolve().parents[1]
BROKER_IMAGE = 'eclipse-mosquitto:2.0.22@sha256:199ea8ef2e35ec2b1b37e59cfd1dbae538ed4dfa4a2251a121a52215a6248a21'


def command(*args):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=900, check=False)
    if result.returncode:
        # Do not echo command arguments or Docker environment files.
        raise RuntimeError(f'{args[0]} operation failed (exit {result.returncode}): {result.stderr[-1500:]}')
    return result.stdout.strip()


def request(url, token=None, data=None, content='application/json', auth=None):
    headers = {'Content-Type': content}
    if token:
        headers['Authorization'] = 'Token ' + token
    if auth:
        headers['Authorization'] = 'Basic ' + base64.b64encode(auth.encode()).decode()
    body = json.dumps(data).encode() if isinstance(data, dict) else data
    try:
        with urlopen(Request(url, data=body, headers=headers), timeout=10) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


def until(check, description, seconds=120):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if check():
                return
        except (OSError, URLError, ValueError):
            pass
        time.sleep(1)
    raise TimeoutError(description)


class Stack:
    def __init__(self, directory):
        self.directory = directory
        self.prefix = 'ot-test-' + secrets.token_hex(4)
        self.containers = []
        self.volumes = []
        command('docker', 'network', 'create', self.prefix)

    def volume(self, name, uid, helper_image):
        name = self.prefix + '-' + name
        command('docker', 'volume', 'create', name)
        self.volumes.append(name)
        # Docker lacks Kubernetes fsGroup. Set ownership on this new test-only
        # volume before starting the same non-root UID used by the deployment.
        command('docker', 'run', '--rm', '--network', 'none', '--user', '0',
                '--cap-drop', 'ALL', '--cap-add', 'CHOWN', '-v', name + ':/volume',
                '--entrypoint', 'chown', helper_image, str(uid) + ':' + str(uid), '/volume')
        return name

    def start(self, name, image, env=None, ports=(), mounts=(), extra=()):
        full = self.prefix + '-' + name
        args = ['docker', 'run', '-d', '--name', full, '--network', self.prefix, '--network-alias', name]
        if env:
            env_path = self.directory / (name + '.env')
            env_path.write_text(''.join(f'{k}={v}\n' for k, v in env.items()))
            env_path.chmod(0o600)
            args += ['--env-file', str(env_path)]
        for port in ports:
            args += ['-p', f'127.0.0.1::{port}']
        for source, target in mounts:
            args += ['-v', f'{source}:{target}:ro']
        args += list(extra) + [image]
        self.containers.append(full)
        command(*args)
        return full

    def endpoint(self, name, port):
        return command('docker', 'port', self.prefix + '-' + name, str(port)).splitlines()[0]

    def close(self):
        for container in reversed(self.containers):
            subprocess.run(['docker', 'rm', '-fv', container], capture_output=True, timeout=60, check=False)
        for volume in self.volumes:
            subprocess.run(['docker', 'volume', 'rm', volume], capture_output=True, timeout=60, check=False)
        subprocess.run(['docker', 'network', 'rm', self.prefix], capture_output=True, timeout=60, check=False)


def platform_image(name):
    documents = yaml.safe_load_all((ROOT/'k3s'/f'{name}-deploy.yaml').read_text())
    return next(d for d in documents if d['kind'] == 'Deployment')['spec']['template']['spec']['containers'][0]['image']


def reading_persisted(stack, token, query, device):
    # Resolve on each query: Docker can reallocate ephemeral ports on restart.
    url = 'http://' + stack.endpoint('influxdb', 8086) + '/api/v2/query?org=lab'
    status, body = request(url, token, {'query': query})
    if status == 429 or status >= 500:
        return False
    if status != 200:
        raise RuntimeError(f'InfluxDB verification query failed (HTTP {status})')
    # Parse actual records, rather than matching device names inside error text.
    lines = [line for line in body.decode('utf-8').splitlines()
             if line and not line.startswith('#')]
    return any(row.get('device') == device for row in csv.DictReader(io.StringIO('\n'.join(lines))))


def publish_checked(client, topic, payload):
    info = client.publish(topic, json.dumps(payload), qos=1)
    if info.rc != mqtt.MQTT_ERR_SUCCESS:
        raise RuntimeError('Test reading was not queued for MQTT publication')
    info.wait_for_publish(timeout=10)
    if not info.is_published():
        raise TimeoutError('Broker did not acknowledge the test reading')


def run(revision):
    image = 'ghcr.io/davidevaloroso-sys/ot-security:'
    with tempfile.TemporaryDirectory(prefix='ot-stack-') as temporary:
        directory = Path(temporary)
        stack = Stack(directory)
        publisher = None
        try:
            password, admin_token = secrets.token_urlsafe(24), secrets.token_urlsafe(48)
            certs = directory/'certs'; certs.mkdir()
            command('openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1', '-subj', '/CN=OT test CA', '-keyout', str(certs/'ca.key'), '-out', str(certs/'ca.crt'))
            command('openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=broker', '-keyout', str(certs/'server.key'), '-out', str(certs/'server.csr'))
            (certs/'extensions').write_text('subjectAltName=DNS:broker,IP:127.0.0.1\nextendedKeyUsage=serverAuth\n')
            command('openssl', 'x509', '-req', '-in', str(certs/'server.csr'), '-CA', str(certs/'ca.crt'), '-CAkey', str(certs/'ca.key'), '-CAcreateserial', '-days', '1', '-extfile', str(certs/'extensions'), '-out', str(certs/'server.crt'))
            config = directory/'broker';config.mkdir()
            for name in ('ca.crt', 'server.crt', 'server.key'):
                shutil.copyfile(certs/name, config/name); (config/name).chmod(0o644)
            (config/'passwords').write_text(''.join(f'{user}:{password}\n' for user in ('raspi-simulator','ia-consumer','ot-mqtt-consumer','nodered')))
            command('docker','run','--rm','-v',f'{config}:/config',BROKER_IMAGE,'mosquitto_passwd','-U','/config/passwords')
            (config/'passwords').chmod(0o644)
            shutil.copyfile(ROOT/'config/mosquitto.acl.example', config/'acl')
            (config/'mosquitto.conf').write_text('listener 8883\nallow_anonymous false\npassword_file /mosquitto/config/passwords\nacl_file /mosquitto/config/acl\ncertfile /mosquitto/config/server.crt\nkeyfile /mosquitto/config/server.key\ntls_version tlsv1.2\npersistence true\npersistence_location /mosquitto/data/\n')
            stack.start('broker',BROKER_IMAGE,ports=(8883,),mounts=((config,'/mosquitto/config'),))
            influx_env={'INFLUXD_BOLT_PATH':'/var/lib/influxdb2/influxd.bolt','INFLUXD_ENGINE_PATH':'/var/lib/influxdb2/engine','INFLUXD_SQLITE_PATH':'/var/lib/influxdb2/influxd.sqlite'}
            volume = stack.volume('influx-data', 1000, image + revision)
            stack.start('influxdb',platform_image('influxdb'),env=influx_env,ports=(8086,),extra=('--user','1000:1000','--read-only','--tmpfs','/tmp:uid=1000,gid=1000','-v',volume + ':/var/lib/influxdb2','--cap-drop','ALL','--security-opt','no-new-privileges'))
            influx='http://'+stack.endpoint('influxdb',8086)
            until(lambda: request(influx+'/health')[0]==200,'InfluxDB startup')
            assert initialize(influx,'testadmin',password,admin_token,'lab','ot')
            assert not initialize(influx,'testadmin',password,admin_token,'lab','ot'), 'Existing database was reinitialized'
            tokens=scoped_tokens(influx,admin_token,'lab','ot')
            common={'MQTT_BROKER':'broker','MQTT_PORT':'8883','MQTT_TLS':'true','MQTT_CA_FILE':'/etc/mqtt/ca.crt','MQTT_PASSWORD':password}
            ca_mount=((certs/'ca.crt','/etc/mqtt/ca.crt'),)
            # Generate bcrypt inside the actual Node-RED image; no host dependency.
            node_image=image+'nodered-'+revision
            hashed=command('docker','run','--rm','--entrypoint','node',node_image,'-e',"console.log(require('bcryptjs').hashSync('integration-admin-only',10))")
            nr_env={**common,'MQTT_USERNAME':'nodered','INFLUXDB_URL':'http://influxdb:8086','INFLUXDB_ORG':'lab','INFLUXDB_BUCKET':'ot','INFLUXDB_TOKEN':tokens['nodered'],'NODE_RED_ADMIN_USER':'testadmin','NODE_RED_ADMIN_PASSWORD_HASH':hashed,'NODE_RED_CREDENTIAL_SECRET':secrets.token_urlsafe(32)}
            stack.start('nodered',node_image,env=nr_env,ports=(1880,),mounts=ca_mount,extra=('--read-only','--tmpfs','/tmp:uid=1000,gid=1000','--tmpfs','/data:uid=1000,gid=1000','--cap-drop','ALL','--security-opt','no-new-privileges'))
            node_url='http://'+stack.endpoint('nodered',1880)
            until(lambda: request(node_url+'/ot-health')[0]==503,'Node-RED flow startup')
            assert request(node_url+'/flows')[0]==401, 'Node-RED flows exposed without login'
            for name,prefix,user in [('audit','','ot-mqtt-consumer'),('inference','ia-consumer-','ia-consumer')]:
                stack.start(name,image+prefix+revision,env={**common,'MQTT_USERNAME':user},mounts=ca_mount)
            until(lambda: command('docker','exec',stack.prefix+'-inference','python','-c',"from pathlib import Path; print(Path('/tmp/ot-health/ot-ready').exists())")=='True','Inference readiness')
            host,port=stack.endpoint('broker',8883).split(':')
            context=ssl.create_default_context(cafile=str(certs/'ca.crt'))
            publisher=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='integration-producer')
            publisher.username_pw_set('raspi-simulator',password);publisher.tls_set_context(context)
            publisher.connect(host,int(port));publisher.loop_start()
            until(publisher.is_connected,'MQTT TLS connection')
            timestamp=int(time.time())
            for topic,value,unit in [('temperature',25,'C'),('humidity',55,'%'),('temperature',150,'C')]:
                payload={'device':'integration','value':value,'unit':unit,'ts':timestamp}
                publish_checked(publisher,'lab/raspi1/'+topic,payload)
                timestamp+=1
            until(lambda: request(node_url+'/ot-health')[0]==200,'Node-RED persisted telemetry')
            query='from(bucket:"ot") |> range(start:-1h, stop:1h) |> filter(fn:(r)=>r._measurement=="ot_anomaly")'
            query_url=influx+'/api/v2/query?org=lab'
            until(lambda: reading_persisted(stack,tokens['grafana'],query,'integration'),'Inference alert persisted in InfluxDB')
            denied_status,denied_body=request(query_url,tokens['nodered'],{'query':query})
            # InfluxDB deliberately hides buckets from tokens without read permission.
            hidden_bucket=(denied_status==404 and b'bucket' in denied_body.lower()
                           and (b'not found' in denied_body.lower() or b'could not find' in denied_body.lower()))
            assert denied_status in (401,403) or hidden_bucket,f'Write token query not denied (HTTP {denied_status})'
            assert request(influx+'/api/v2/write?org=lab&bucket=ot',tokens['grafana'],b'x value=1','text/plain')[0] in (401,403),'Read token must not write'
            org_id=json.loads(request(influx+'/api/v2/orgs?org=lab',admin_token)[1])['orgs'][0]['id']
            assert request(influx+'/api/v2/authorizations',tokens['nodered'],{'orgID':org_id,'permissions':[{'action':'read','resource':{'type':'buckets','orgID':org_id}}]})[0] in (401,403),'Write token must not create authorizations'
            stack.start('simulator',image+'raspi-simulator-'+revision,env={**common,'MQTT_USERNAME':'raspi-simulator','PUBLISH_INTERVAL':'1'},mounts=ca_mount)
            mounts=((ROOT/'platform/grafana/datasource.yaml','/etc/grafana/provisioning/datasources/ot.yaml'),(ROOT/'platform/grafana/provider.yaml','/etc/grafana/provisioning/dashboards/ot.yaml'),(ROOT/'platform/grafana/ot-security.json','/etc/grafana/ot-dashboards/ot-security.json'))
            stack.start('grafana',image+'grafana-'+revision,env={'GF_SECURITY_ADMIN_USER':'testadmin','GF_SECURITY_ADMIN_PASSWORD':password,'GF_AUTH_ANONYMOUS_ENABLED':'false','INFLUXDB_ORG':'lab','INFLUXDB_BUCKET':'ot','INFLUXDB_READ_TOKEN':tokens['grafana']},ports=(3000,),mounts=mounts,extra=('--user','472:472','--read-only','--tmpfs','/tmp:uid=472,gid=472','--tmpfs','/var/lib/grafana:uid=472,gid=472','--cap-drop','ALL','--security-opt','no-new-privileges'))
            grafana='http://'+stack.endpoint('grafana',3000);auth='testadmin:'+password
            until(lambda: request(grafana+'/api/health')[0]==200,'Grafana startup')
            until(lambda: request(grafana+'/api/dashboards/uid/ot-security',auth=auth)[0]==200,'Dashboard provisioning')
            status,raw=request(grafana+'/api/dashboards/uid/ot-security',auth=auth)
            assert status==200,'Provisioned dashboard missing'
            dashboard=json.loads(raw)['dashboard']; assert len(dashboard['panels'])==6
            until(lambda: request(grafana+'/api/datasources/uid/ot-influxdb/health',auth=auth)[0]==200,
                  'Grafana datasource startup')
            status,raw=request(grafana+'/api/datasources/uid/ot-influxdb/health',auth=auth)
            assert status==200 and json.loads(raw)['status']=='OK','Grafana datasource health failed'
            # Execute every actual dashboard query through Grafana's datasource proxy.
            for panel in dashboard['panels']:
                if not panel.get('targets'):continue
                query=panel['targets'][0]['query']
                body={'from':str((int(time.time())-3600)*1000),'to':str((int(time.time())+60)*1000),'queries':[{'refId':'A','datasource':{'uid':'ot-influxdb','type':'influxdb'},'query':query,'intervalMs':1000,'maxDataPoints':1000}]}
                status,raw=request(grafana+'/api/ds/query',data=body,auth=auth)
                response=json.loads(raw)
                assert status==200 and not response['results']['A'].get('error'),f'Grafana panel failed: {panel["title"]}'
                assert response['results']['A'].get('frames'),f'Grafana panel returned no frames: {panel["title"]}'
            # Recover after a real database outage; broker retains unacknowledged QoS1 input.
            command('docker','stop',stack.prefix+'-influxdb')
            publish_checked(publisher,'lab/raspi1/temperature',{'device':'recovery','value':26,'unit':'C','ts':int(time.time())})
            until(lambda: request(node_url+'/ot-health')[0]==503,'Readiness during database outage',30)
            command('docker','start',stack.prefix+'-influxdb')
            # Docker may allocate a different ephemeral host port on restart.
            # Node-RED uses the stable internal address, but the host query must
            # resolve the current published port before checking persistence.
            influx='http://'+stack.endpoint('influxdb',8086)
            until(lambda: request(influx+'/health')[0]==200,'Restarted InfluxDB endpoint')
            until(lambda: request(node_url+'/ot-health')[0]==200,'Database recovery')
            recovery='from(bucket:"ot") |> range(start:-1h) |> filter(fn:(r)=>r.device=="recovery")'
            until(lambda: reading_persisted(stack,tokens['grafana'],recovery,'recovery'),'Recovery reading persisted')
            print('PASS: TLS MQTT -> Python inference + Node-RED -> InfluxDB -> all Grafana panels; token isolation, login and outage recovery')
        finally:
            if publisher:
                publisher.disconnect();publisher.loop_stop()
            stack.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('revision',help='Full SHA of the five locally built/scanned images')
    args=parser.parse_args()
    if len(args.revision)!=40 or any(c not in '0123456789abcdef' for c in args.revision):
        parser.error('Expected full commit SHA')
    run(args.revision)
