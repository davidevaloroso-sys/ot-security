"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");
const net = require("node:net");
const {once} = require("node:events");
const {setTimeout: delay} = require("node:timers/promises");
const aedes = require("aedes");
const mqtt = require("mqtt");
const {Bridge, configuration} = require("../bridge");
const {TEMPERATURE} = require("../contract");

async function until(predicate) {
    for (let i = 0; i < 100; i++) { if (predicate()) return; await delay(50); }
    throw new Error("Timed out");
}
test("real MQTT delivery is acknowledged only after HTTP 204; retries preserve reading", async t => {
    const broker = aedes();
    const server = net.createServer(broker.handle);
    server.listen(0, "127.0.0.1"); await once(server, "listening");
    let writes = 0, acknowledged = false, persisted = false;
    broker.on("ack", (_packet, client) => { if (client.id === "ingest-test") acknowledged = true; });
    const influx = http.createServer((req, res) => {
        assert.equal(req.headers.authorization, "Token test-only-token");
        assert.match(req.url, /^\/api\/v2\/write\?org=lab&bucket=ot&precision=s$/);
        const chunks = [];
        req.on("data", b => chunks.push(b));
        req.on("end", () => {
            assert.match(Buffer.concat(chunks).toString(), /^ot_telemetry,/);
            writes++;
            if (writes === 1) { assert.equal(acknowledged, false); res.writeHead(503).end(); }
            else { assert.equal(acknowledged, false); persisted = true; res.writeHead(204).end(); }
        });
    });
    influx.listen(0, "127.0.0.1"); await once(influx, "listening");
    const config = configuration({MQTT_BROKER: "127.0.0.1", MQTT_PORT: server.address().port, MQTT_TLS: "false", MQTT_ALLOW_INSECURE_LOCAL: "true", MQTT_USERNAME: "test", MQTT_PASSWORD: "test-only", MQTT_CLIENT_ID: "ingest-test", INFLUXDB_URL: `http://127.0.0.1:${influx.address().port}`, INFLUXDB_ORG: "lab", INFLUXDB_BUCKET: "ot", INFLUXDB_TOKEN: "test-only-token"});
    const bridge = new Bridge(config).start();
    const publisher = mqtt.connect({host:"127.0.0.1",port:server.address().port,clientId:"producer-test"});
    t.after(async () => { await publisher.endAsync(true); await bridge.close(); await new Promise(r => broker.close(r)); server.close(); influx.close(); });
    await once(publisher, "connect");
    await until(() => bridge.state.subscribed);
    await publisher.publishAsync(TEMPERATURE, JSON.stringify({device:"raspi1",value:25,unit:"C",ts:1760000000}), {qos:1});
    await until(() => acknowledged);
    assert.equal(persisted, true); assert.equal(writes, 2); assert.equal(bridge.ready, true);
    await publisher.publishAsync(TEMPERATURE, '{"value":NaN}', {qos:1});
    await until(() => bridge.state.rejected === 1);
    assert.equal(writes, 2);
});
test("TLS checks cannot be disabled accidentally", () => {
    const env = {MQTT_BROKER:"host",MQTT_USERNAME:"test",MQTT_PASSWORD:"test-only",INFLUXDB_URL:"http://influxdb:8086",INFLUXDB_ORG:"lab",INFLUXDB_BUCKET:"ot",INFLUXDB_TOKEN:"test-only"};
    const config=configuration(env);
    assert.equal(config.options.protocol,"mqtts"); assert.equal(config.options.rejectUnauthorized,true); assert.equal(config.options.clean,false);
    assert.throws(() => configuration({...env,MQTT_TLS:"false"}));
});
test("disconnect cancels the old database retry without acknowledging input", async () => {
    const bridge = new Bridge({});
    let attempts = 0;
    bridge.write = async () => { attempts++; throw new Error('offline'); };
    const connection = new AbortController();
    const operation = bridge.process({topic:TEMPERATURE,payload:Buffer.from(JSON.stringify({device:'raspi1',value:25,unit:'C',ts:1760000000}))}, connection.signal);
    await until(() => attempts > 0);
    connection.abort();
    await assert.rejects(operation, /connection closed/i);
    const stoppedAt = attempts; await delay(400);
    assert.equal(attempts, stoppedAt);
    assert.equal(bridge.state.written, 0);
});
