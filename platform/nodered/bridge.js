"use strict";
const fs = require("node:fs");
const mqtt = require("mqtt");
const {setTimeout: delay} = require("node:timers/promises");
const {reading, TEMPERATURE, HUMIDITY, ANOMALY} = require("./contract");

function configuration(env = process.env) {
    const required = ["MQTT_BROKER", "MQTT_USERNAME", "MQTT_PASSWORD", "INFLUXDB_URL", "INFLUXDB_ORG", "INFLUXDB_BUCKET", "INFLUXDB_TOKEN"];
    for (const name of required) if (!env[name]) throw new Error(`Missing ${name}`);
    const secure = env.MQTT_TLS !== "false";
    if (env.MQTT_TLS && !["true", "false"].includes(env.MQTT_TLS)) throw new Error("Invalid MQTT_TLS");
    if (!secure && env.MQTT_ALLOW_INSECURE_LOCAL !== "true") throw new Error("Plaintext MQTT requires explicit test opt-in");
    const options = {
        host: env.MQTT_BROKER, port: Number(env.MQTT_PORT || 8883),
        protocol: secure ? "mqtts" : "mqtt", protocolVersion: 4,
        username: env.MQTT_USERNAME, password: env.MQTT_PASSWORD,
        clientId: env.MQTT_CLIENT_ID || "nodered-ingest-1", clean: false,
        reconnectPeriod: 2000, connectTimeout: 10000, keepalive: 30,
        rejectUnauthorized: true, minVersion: "TLSv1.2", resubscribe: false
    };
    if (!Number.isInteger(options.port) || options.port < 1 || options.port > 65535) throw new Error("Invalid MQTT_PORT");
    if (secure && env.MQTT_CA_FILE) options.ca = fs.readFileSync(env.MQTT_CA_FILE);
    const endpoint = new URL("/api/v2/write", env.INFLUXDB_URL);
    if (!['http:', 'https:'].includes(endpoint.protocol) || endpoint.username || endpoint.password) throw new Error("Invalid InfluxDB URL");
    endpoint.search = new URLSearchParams({org: env.INFLUXDB_ORG, bucket: env.INFLUXDB_BUCKET, precision: "s"}).toString();
    return {options, endpoint, token: env.INFLUXDB_TOKEN};
}

class Bridge {
    constructor(config, notify = () => {}, report = () => {}) {
        this.config = config;
        this.notify = notify;
        this.report = report;
        this.state = {mqtt: false, subscribed: false, database: false, written: 0, rejected: 0, retries: 0};
        this.abort = new AbortController();
    }
    get ready() { return this.state.mqtt && this.state.subscribed && this.state.database; }
    async write(line, signal = this.abort.signal) {
        const response = await fetch(this.config.endpoint, {
            method: "POST", headers: {Authorization: `Token ${this.config.token}`, "Content-Type": "text/plain; charset=utf-8"},
            body: line, redirect: "error",
            signal: AbortSignal.any([signal, this.abort.signal, AbortSignal.timeout(5000)])
        });
        const body = await response.text();
        if (response.status !== 204) {
            const error = new Error(`InfluxDB write HTTP ${response.status}`);
            error.status = response.status;
            let detail;
            try { detail = JSON.parse(body); } catch (_) { /* No response body is logged. */ }
            error.permanentPoint = response.status === 413 || response.status === 422 ||
                (response.status === 400 && detail?.code === 'invalid' &&
                 typeof detail.message === 'string' && /^unable to parse(?: |:)/i.test(detail.message));
            throw error;
        }
    }
    async process(packet, signal = this.abort.signal) {
        let record;
        try { record = reading(packet.topic, packet.payload); }
        catch (_) { this.state.rejected++; this.report("Invalid telemetry discarded"); return; }
        let backoff = 250;
        while (!signal.aborted && !this.abort.signal.aborted) {
            try {
                await this.write(record.line, signal);
                this.state.database = true;
                this.state.written++;
                this.notify({payload: {device: record.device, kind: record.kind, measurement: record.measurement, persisted: true}});
                return;
            } catch (error) {
                // Each request contains one point. Retrying a permanently
                // rejected point would block every following MQTT delivery.
                if (error.permanentPoint) {
                    this.state.rejected++;
                    this.report(`Telemetry rejected by InfluxDB (HTTP ${error.status}); discarded`);
                    return;
                }
                this.state.database = false;
                if (signal.aborted || this.abort.signal.aborted) throw new Error("Ingestion connection closed");
                this.state.retries++;
                if (this.state.retries === 1 || this.state.retries % 30 === 0) this.report("InfluxDB unavailable or write rejected; retrying without MQTT ACK");
                await delay(backoff, null, {signal: AbortSignal.any([signal, this.abort.signal])}).catch(() => {});
                backoff = Math.min(backoff * 2, 10000);
            }
        }
        throw new Error("Ingestion connection closed");
    }
    start() {
        this.client = mqtt.connect(this.config.options);
        this.client.on("error", () => this.report("MQTT connection error; check TLS, ACL and credentials"));
        this.client.on("connect", () => {
            this.connection?.abort();
            this.connection = new AbortController();
            this.state.mqtt = true;
            this.client.subscribe([TEMPERATURE, HUMIDITY, ANOMALY], {qos: 1}, (error, granted) => {
                this.state.subscribed = !error && granted?.length === 3 && granted.every(g => g.qos === 1);
            });
        });
        this.client.on("close", () => { this.connection?.abort(); this.state.mqtt = false; this.state.subscribed = false; });
        // MQTT.js processes one packet at a time. PUBACK follows this callback,
        // so broker backpressure and persistent sessions cover a database outage.
        this.client.handleMessage = (packet, done) => {
            const signal = this.connection?.signal || this.abort.signal;
            this.process(packet, signal).then(() => {
                if (!signal.aborted && !this.abort.signal.aborted) done();
                else done(new Error("Connection closed before acknowledgement"));
            }).catch(error => done(error));
        };
        return this;
    }
    async close() {
        this.abort.abort();
        this.state.mqtt = false;
        if (this.client) await this.client.endAsync(true);
    }
}
module.exports = {Bridge, configuration};
