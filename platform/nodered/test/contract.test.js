"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const {reading, TEMPERATURE, ANOMALY} = require("../contract");
const sample = {device: "raspi1", value: 25, unit: "C", ts: 1760000000, in_range: true};
const encode = value => Buffer.from(JSON.stringify(value));
test("temperature line protocol with deterministic timestamp", () => {
    assert.equal(reading(TEMPERATURE, encode(sample)).line, "ot_telemetry,device=raspi1,kind=temperature,unit=C value=25,in_range=true 1760000000");
});
for (const [key, value] of [["value", "25"], ["value", null], ["ts", -1], ["ts", 1.5], ["ts", 1e15], ["device", "a\nb"], ["unit", "%"], ["in_range", 1]]) {
    test(`rejects invalid ${key}=${value}`, () => assert.throws(() => reading(TEMPERATURE, encode({...sample, [key]: value}))));
}
test("strict UTF-8, JSON, payload size and supported topics", () => {
    for (const bytes of [Buffer.from([0xff]), Buffer.from('{"value":NaN}'), Buffer.alloc(16385)]) assert.throws(() => reading(TEMPERATURE, bytes));
    assert.throws(() => reading("other/topic", encode(sample)));
});
test("anomaly event ID is a field, not an unbounded tag", () => {
    const line = reading(ANOMALY, encode({...sample, topic: TEMPERATURE, model_alert: true, model_anomaly_score: 0.9, event_id: "a".repeat(64)})).line;
    assert.match(line, /^ot_anomaly,device=raspi1,kind=temperature,unit=C /);
    assert.match(line, /score=0.9,model_alert=true,event_id="a{64}"/);
});
