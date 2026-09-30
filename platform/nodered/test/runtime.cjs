// Real Node-RED runtime smoke. Set NODE_RED_RUNTIME to the installed red.js.
const assert = require('node:assert/strict');
const {spawn, spawnSync} = require('node:child_process');
const {once} = require('node:events');
const {setTimeout: delay} = require('node:timers/promises');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const net = require('node:net');
const mqtt = require('mqtt');
const aedes = require('aedes');

(async () => {
  assert(process.env.NODE_RED_RUNTIME, 'NODE_RED_RUNTIME required');
  const root = path.resolve(__dirname, '../../..');
  const runtime = path.resolve(process.env.NODE_RED_RUNTIME);
  const registry = require.resolve('@node-red/registry/package.json', {paths:[path.dirname(runtime)]});
  const npmManifest = require.resolve('npm/package.json', {paths:[path.dirname(registry)]});
  assert.equal(require(npmManifest).name, '@ot-security/disabled-npm', 'runtime must not embed the npm installer');
  for (const args of [['--version'], ['install', 'test-argument-must-not-be-logged']]) {
    const denied = spawnSync(process.execPath, [path.join(path.dirname(npmManifest), 'bin/npm-cli.js'), ...args],
      {encoding:'utf8', windowsHide:true, timeout:5000});
    assert.equal(denied.status, 1, 'package manager adapter must reject every invocation');
    assert.equal(denied.stdout, '');
    assert.match(denied.stderr, /Runtime package installation is disabled/);
    assert(!denied.stderr.includes('test-argument-must-not-be-logged'));
  }
  const bcrypt = require(require.resolve('bcryptjs', {paths:[path.dirname(runtime)]}));
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ot-runtime-'));
  const broker = aedes(); const tcp = net.createServer(broker.handle);
  tcp.listen(0, '127.0.0.1'); await once(tcp, 'listening');
  let writes = 0;
  const db = http.createServer((req,res) => {req.resume();req.on('end',()=>{writes++;res.writeHead(204).end();});});
  db.listen(0,'127.0.0.1'); await once(db,'listening');
  const reservation=net.createServer();reservation.listen(0,'127.0.0.1');await once(reservation,'listening');
  const port=reservation.address().port;await new Promise(r=>reservation.close(r));
  const env={...process.env, PORT:String(port),NODE_RED_HOST:'127.0.0.1',NODE_RED_USER_DIR:dir,
    NODE_RED_ADMIN_USER:'testadmin',NODE_RED_ADMIN_PASSWORD_HASH:bcrypt.hashSync('test-only-password',10),NODE_RED_CREDENTIAL_SECRET:'test-only-credential-secret',
    OT_NODES_DIR:path.join(root,'platform/nodered'),OT_FLOW_FILE:path.join(root,'platform/nodered/flows.json'),
    MQTT_BROKER:'127.0.0.1',MQTT_PORT:String(tcp.address().port),MQTT_TLS:'false',MQTT_ALLOW_INSECURE_LOCAL:'true',
    MQTT_USERNAME:'test',MQTT_PASSWORD:'test-only',INFLUXDB_URL:`http://127.0.0.1:${db.address().port}`,INFLUXDB_ORG:'lab',INFLUXDB_BUCKET:'ot',INFLUXDB_TOKEN:'test-only'};
  const child=spawn(process.execPath,[runtime,'--settings',path.join(root,'config/nodered-settings.js')],{env,windowsHide:true,stdio:['ignore','pipe','pipe']});
  let logs='';child.stdout.on('data',b=>logs+=b);child.stderr.on('data',b=>logs+=b);
  let publisher;
  try {
    const base=`http://127.0.0.1:${port}`;
    let available=false;
    for(let i=0;i<120;i++){try{const r=await fetch(base+'/ot-health');if(r.status===503){available=true;break;}}catch{}await delay(250);}
    assert(available, 'runtime did not load health endpoint');
    assert.equal((await fetch(base+'/flows')).status,401,'flows require authentication');
    const auth=await fetch(base+'/auth/token',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({client_id:'node-red-admin',grant_type:'password',scope:'*',username:'testadmin',password:'test-only-password'})});
    assert.equal(auth.status,200);const token=(await auth.json()).access_token;assert(token);
    const flows=await fetch(base+'/flows',{headers:{Authorization:`Bearer ${token}`}});
    assert.equal(flows.status,200);assert((await flows.json()).some(n=>n.type==='ot-ingest'));
    const install = await fetch(base+'/nodes', {method:'POST', headers:{
      Authorization:`Bearer ${token}`, 'Content-Type':'application/json'},
      body:JSON.stringify({module:'ot-runtime-install-must-remain-disabled'})});
    assert(install.status >= 400, 'runtime module installation must remain disabled for administrators');
    publisher=mqtt.connect({host:'127.0.0.1',port:tcp.address().port});await once(publisher,'connect');
    await publisher.publishAsync('lab/raspi1/temperature',JSON.stringify({device:'raspi1',unit:'C',value:25,ts:1760000000}),{qos:1});
    for(let i=0;i<80 && writes===0;i++)await delay(100);
    assert.equal(writes,1);assert.equal((await fetch(base+'/ot-health')).status,200);
    console.log('PASS: Node-RED loads the flow, enforces login, denies runtime installation and persists MQTT input');
  } catch(error){console.error(logs);throw error;}
  finally{if(publisher)await publisher.endAsync(true);child.kill();await once(child,'exit').catch(()=>{});await new Promise(r=>broker.close(r));tcp.close();db.close();fs.rmSync(dir,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exitCode=1;});
