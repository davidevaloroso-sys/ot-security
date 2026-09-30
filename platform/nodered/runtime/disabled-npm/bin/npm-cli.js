"use strict";
// Node-RED resolves npm/package.json at startup even when its installer is off.
// This is a denial adapter, not npm: no arguments, environment or tokens are logged.
process.stderr.write("Runtime package installation is disabled. Rebuild the OT Security image to change nodes.\n");
process.exitCode = 1;
