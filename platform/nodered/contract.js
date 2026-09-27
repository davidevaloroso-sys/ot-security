"use strict";

const TEMPERATURE = "lab/raspi1/temperature";
const HUMIDITY = "lab/raspi1/humidity";
const ANOMALY = "lab/raspi1/anomaly";
const decoder = new TextDecoder("utf-8", {fatal: true});

function tag(value) {
    return value.replace(/\\/g, "\\\\").replace(/([ ,=])/g, "\\$1");
}
function string(value) {
    return '"' + value.replace(/\\/g, "\\\\").replace(/"/g, '\\"') + '"';
}
function reading(topic, bytes) {
    if (bytes.length > 16384) throw new Error("Payload exceeds 16 KiB");
    const data = JSON.parse(decoder.decode(bytes));
    if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error("Expected object");
    if (typeof data.device !== "string" || !/^[A-Za-z0-9_.:-]{1,128}$/.test(data.device)) throw new Error("Invalid device");
    if (!Number.isFinite(data.value) || typeof data.value !== "number") throw new Error("Invalid value");
    if (!Number.isSafeInteger(data.ts) || data.ts < 0 || data.ts > 9223372036) throw new Error("Invalid timestamp");
    const source = topic === ANOMALY ? data.topic : topic;
    const kind = source === TEMPERATURE ? "temperature" : source === HUMIDITY ? "humidity" : null;
    if (!kind || data.unit !== (kind === "temperature" ? "C" : "%")) throw new Error("Topic/unit mismatch");
    if (data.in_range !== undefined && typeof data.in_range !== "boolean") throw new Error("Invalid in_range");
    if (data.alert != null && (typeof data.alert !== "string" || /[\r\n]/.test(data.alert) || data.alert.length > 128)) throw new Error("Invalid alert");
    let fields = `value=${data.value}`;
    if (topic === ANOMALY) {
        if (data.model_alert !== true || !Number.isFinite(data.model_anomaly_score) || data.model_anomaly_score < 0 || data.model_anomaly_score > 1 || !/^[a-f0-9]{64}$/.test(data.event_id)) throw new Error("Invalid anomaly");
        fields += `,score=${data.model_anomaly_score},model_alert=true,event_id=${string(data.event_id)}`;
    } else {
        if (data.in_range !== undefined) fields += `,in_range=${data.in_range}`;
        if (data.alert != null) fields += `,sensor_alert=${string(data.alert)}`;
    }
    const measurement = topic === ANOMALY ? "ot_anomaly" : "ot_telemetry";
    return {line: `${measurement},device=${tag(data.device)},kind=${kind},unit=${tag(data.unit)} ${fields} ${data.ts}`, device: data.device, kind, measurement};
}
module.exports = {reading, TEMPERATURE, HUMIDITY, ANOMALY};
