"use strict";
const {Bridge, configuration} = require("./bridge");

module.exports = function(RED) {
    let current;
    RED.httpAdmin.get("/ot-health", (_req, res) => res.status(current?.bridge?.ready ? 200 : 503).json({ready: Boolean(current?.bridge?.ready)}));
    function OTIngest(config) {
        RED.nodes.createNode(this, config);
        const node = this;
        current = node;
        try {
            node.bridge = new Bridge(configuration(), msg => node.send(msg), message => node.warn(message)).start();
            node.timer = setInterval(() => node.status({fill: node.bridge.ready ? "green" : "yellow", shape: "dot", text: node.bridge.ready ? "MQTT → InfluxDB" : "waiting for persisted telemetry"}), 2000);
        } catch (error) { node.error(error.message); node.status({fill: "red", shape: "ring", text: "configuration error"}); }
        node.on("close", async (_removed, done) => {
            if (current === node) current = undefined;
            clearInterval(node.timer);
            if (node.bridge) await node.bridge.close();
            done();
        });
    }
    RED.nodes.registerType("ot-ingest", OTIngest);
};
