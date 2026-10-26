FROM nodered/node-red:5.0.9-24@sha256:e085d4a06591fd0aca2ea2a91364d27f1a0e31e885675f77935e10f95412a963
USER root
COPY platform/nodered/runtime/package*.json /usr/src/node-red/
COPY platform/nodered/runtime/.npmrc /usr/src/node-red/.npmrc
COPY platform/nodered/runtime/disabled-npm /usr/src/node-red/disabled-npm
RUN apk upgrade --no-cache \
    && npm ci --prefix /usr/src/node-red --omit=dev --ignore-scripts --no-audit --no-fund
WORKDIR /opt/ot-node
COPY platform/nodered/package*.json ./
RUN npm ci --omit=dev --ignore-scripts --no-audit --no-fund
COPY platform/nodered/contract.js platform/nodered/bridge.js platform/nodered/ot-ingest.js platform/nodered/ot-ingest.html ./
COPY platform/nodered/flows.json /opt/ot/flows.json
COPY config/nodered-settings.js /opt/ot/settings.js
RUN chown -R 1000:1000 /opt/ot /opt/ot-node \
    && npm uninstall -g npm
USER 1000
WORKDIR /usr/src/node-red
ENV NODE_PATH=/usr/src/node-red/node_modules:/opt/ot-node/node_modules
ENTRYPOINT ["node", "/usr/src/node-red/node_modules/node-red/red.js"]
CMD ["--userDir", "/data", "--settings", "/opt/ot/settings.js"]
