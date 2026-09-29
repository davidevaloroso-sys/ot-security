# Inventario della base Grafana

La candidata Grafana comprende una base DHI fissata a digest e il plugin InfluxDB 13.1.6 scaricato dall'API ufficiale Grafana, con SHA256 controllato nel Dockerfile. Il plugin è firmato da Grafana; la verifica delle firme plugin del runtime resta abilitata. Non vengono installati plugin all'avvio.

Trivy sul filesystem non rileva tutte le dipendenze dei binari della base DHI. Per questo il gate scansiona **sia l'immagine finale sia il suo inventario SPDX upstream**, senza esclusioni CVE, VEX o `ignore-unfixed`. Il report SPDX del 29/09/2026 contiene 551 package entries (550 componenti più la radice) e passa il gate HIGH/CRITICAL, insieme all'immagine comprensiva del plugin.

`platform/grafana/security/provenance.json` registra digest dell'indice, piattaforma Linux/amd64, digest dell'immagine per piattaforma, attestazione firmata e checksum del predicato SPDX conservato senza modifiche. `verify_platform_sbom.py` impedisce di aggiornare la base senza aggiornare l'inventario e rileva modifiche al documento. `.gitattributes` preserva i byte attraverso checkout Windows/Linux.

## Aggiornamento

1. Selezionare un digest DHI compatibile e verificarne la distinta firmata con Docker Scout. Per la versione attuale:

```bash
docker scout attest get \
  registry://dhi.io/grafana@sha256:686af1d55ed4d98447691028fd46bdd40833fd053df0144980fabca05a8f3382 \
  --predicate-type https://spdx.dev/Document --platform linux/amd64 \
  --verify --skip-tlog --predicate --output base-sbom.spdx.json
```

2. La firma deve verificarsi contro la chiave pubblica Docker. `--skip-tlog` omette soltanto il controllo Rekor: Docker documenta che alcune attestazioni DHI non sono nel registro pubblico. La firma e i claims devono comunque essere validi. Registrare i nuovi digest e l'hash SHA256, conservare il documento originale e aggiornare il `FROM` del Dockerfile.
3. Eseguire `python scripts/verify_platform_sbom.py`, build, scansione immagine+SPDX e integrazione completa. Non usare un inventario di una piattaforma o release diversa.
4. Per aggiornare il plugin, confrontare lo SHA256 dell'archivio Linux/amd64 con quello restituito da `https://grafana.com/api/plugins/influxdb/versions/<versione>`, aggiornare versione/hash nel Dockerfile e ricostruire. Il binario deve essere incluso nella scansione e le query Flux devono passare il collaudo.

Durante l'analisi, il formato CycloneDX upstream attribuiva il nome senza scope `js-cookie` al package `pkg:npm/%40types/js-cookie@2.2.7`, causando una segnalazione falsa. L'SPDX firmato identifica correttamente `@types/js-cookie`: non sono state alterate versioni, rimosse dipendenze o introdotte eccezioni allo scanner.

Fonti: [verifica delle attestazioni DHI](https://docs.docker.com/dhi/how-to/verify/), [catalogo della base esatta](https://hub.docker.com/hardened-images/catalog/dhi/grafana/images/grafana%2Fdebian-13%2F13.2/sha256-7ffc0551ec95e0890d23168cf601b399cc35f983f053529e3733688f43c4734a/specifications), [plugin InfluxDB ufficiale](https://grafana.com/grafana/plugins/influxdb/).
