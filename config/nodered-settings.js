"use strict";
const required = ["NODE_RED_ADMIN_USER", "NODE_RED_ADMIN_PASSWORD_HASH", "NODE_RED_CREDENTIAL_SECRET"];
for (const key of required) {
    if (!process.env[key]) throw new Error(`Missing ${key}`);
}
if (!/^\$2[aby]\$\d{2}\$/.test(process.env.NODE_RED_ADMIN_PASSWORD_HASH)) {
    throw new Error("Expected a bcrypt password hash");
}
module.exports = {
    uiPort: Number(process.env.PORT || 1880),
    uiHost: process.env.NODE_RED_HOST || "0.0.0.0",
    userDir: process.env.NODE_RED_USER_DIR || "/data",
    nodesDir: process.env.OT_NODES_DIR || "/opt/ot-node",
    flowFile: process.env.OT_FLOW_FILE || "/opt/ot/flows.json",
    flowFilePretty: true,
    readOnly: true,
    editorTheme: {page: {title: "OT Security · Node-RED"}, palette: {editable: false}},
    credentialSecret: process.env.NODE_RED_CREDENTIAL_SECRET,
    adminAuth: {type: "credentials", users: [{
        username: process.env.NODE_RED_ADMIN_USER,
        password: process.env.NODE_RED_ADMIN_PASSWORD_HASH,
        permissions: "*"
    }]},
    // No unauthenticated custom HTTP endpoints until explicitly configured.
    httpNodeRoot: false,
    externalModules: {autoInstall: false, palette: {allowInstall: false, allowUpload: false}},
    logging: {console: {level: "info", metrics: false, audit: true}}
};
