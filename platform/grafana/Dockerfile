FROM python:3.11-alpine@sha256:cd04730b8511def3fbf14204d66a0c1536f290b8e896ed5a94cd64cb15ac1356 AS plugin
WORKDIR /plugin
# Official signed InfluxDB plugin, pinned to Grafana's published archive SHA256.
RUN wget -q 'https://grafana.com/api/plugins/influxdb/versions/13.1.6/download?os=linux&arch=amd64' -O influxdb.zip \
    && echo 'ebf559b2a3d2375efe7959568a132c16ebe1fe7c55bfaf2ce7643693d6b0bceb  influxdb.zip' | sha256sum -c - \
    && unzip -q influxdb.zip \
    && chmod 755 influxdb/gpx_grafana_influxdb_datasource_linux_amd64

FROM dhi.io/grafana:13.2.2@sha256:686af1d55ed4d98447691028fd46bdd40833fd053df0144980fabca05a8f3382
# Install outside the data PVC; runtime cannot replace the scanned plugin.
COPY --from=plugin --chown=472:472 /plugin/influxdb /opt/ot-plugins/influxdb
ENV GF_PATHS_PLUGINS=/opt/ot-plugins \
    GF_PLUGINS_PREINSTALL_DISABLED=true \
    GF_PLUGINS_PLUGIN_ADMIN_ENABLED=false \
    GF_ANALYTICS_CHECK_FOR_UPDATES=false \
    GF_ANALYTICS_CHECK_FOR_PLUGIN_UPDATES=false
USER 472
