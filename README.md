# OT Security — laboratorio MQTT, IA e osservabilità

## Stato operativo — 30 settembre 2026

Il run `36743791003` sul commit `15fc489` si è fermato nell'audit npm del runtime Node-RED, prima di build e deploy: `axios 1.19.0` HIGH e `moment 2.30.1` MODERATE. Aggiornati gli override e il lockfile a `axios 1.20.0` e `moment 2.31.0`. Installazione pulita e audit riportano zero vulnerabilità; il collaudo del runtime reale supera avvio, login e ingestione MQTT. Il gate di sicurezza resta attivo.

La preparazione MQTT sulla VM è completata: TLS/IP SAN e quattro login verificati, tre Secret MQTT e `mqtt-ca` creati. La [CI 36740613024](https://github.com/davidevaloroso-sys/ot-security/actions/runs/36740613024) ha superato tutti i gate e la pubblicazione; il deploy si è fermato prima dell'apply perché mancavano soltanto `grafana-influxdb` e `nodered-auth`. La pipeline ora esegue `prepare_observability.py --apply` prima del preflight: prepara solo i Secret assenti, con token emessi dall'InfluxDB esistente e login Node-RED bcrypt. Conserva i Secret presenti, non inizializza il database e non modifica i vecchi file Node-RED. Dettagli e limiti in [K3S-SECRETS.md](docs/K3S-SECRETS.md#preparazione-automatica-di-node-red-e-grafana).

La suite locale aggiornata passa 165 test Python. Le sei build Docker, scansioni HIGH/CRITICAL e integrazione completa della release precedente hanno verificato MQTT TLS, inferenza, token limitati, tutti i pannelli Grafana e recupero dopo un guasto InfluxDB. Il modello mantiene identiche probabilità sulle 10.000 righe del dataset anche nell'immagine Alpine Python 3.11.

Le immagini candidate e l'inventario SPDX firmato della base Grafana non riportano HIGH/CRITICAL nelle scansioni locali del 29 settembre. Nessuna esclusione CVE è stata aggiunta. Il [run remoto 36628560125](https://github.com/davidevaloroso-sys/ot-security/actions/runs/36628560125), sul commit `b70bd07`, ha superato test, sei build, scansioni, integrazione e publish. VPN, API privata e TLS funzionano; il deploy si è fermato nel preflight prima dell'apply. L'inventario del proprietario conferma cinque Secret applicativi e il ConfigMap `mqtt-ca` ancora assenti. I deployment esistenti sono della versione precedente: il nuovo rollout non è avvenuto. Preparazione in [docs/K3S-SECRETS.md](docs/K3S-SECRETS.md), rete in [docs/K3S-TLS.md](docs/K3S-TLS.md), attività in [docs/REMEDIATION-STATUS.md](docs/REMEDIATION-STATUS.md).

Pipeline di laboratorio su K3s: telemetria autenticata, validazione, inferenza e dashboard provisionata dal codice. API K3s (`6443`) e broker MQTT (`8883`) sono sulla VM **192.168.1.21**. Il DDNS **k3s--lab.cloud-ip.cc:51820/UDP** individua l'endpoint pubblico WireGuard; attraverso il tunnel il runner interroga direttamente **https://192.168.1.21:6443**.

Il successivo [run 36657062263](https://github.com/davidevaloroso-sys/ot-security/actions/runs/36657062263) si è fermato prima delle build per un avviso HIGH su `undici` nell'npm incorporato da Node-RED. Il runtime ora rimuove quel gestore, già disabilitato dalle impostazioni, e include un adattatore locale che rifiuta ogni invocazione. L'audit del nuovo lockfile riporta zero vulnerabilità e lo smoke Node-RED reale verifica login, flusso MQTT e rifiuto dell'installazione anche per l'amministratore. Nessun controllo di sicurezza è stato disabilitato.

Il [run 36658383049](https://github.com/davidevaloroso-sys/ot-security/actions/runs/36658383049), commit `efb17b5`, conferma test/training, tutte le sei build, scansioni, integrazione e publish superati. Il deploy raggiunge K3s `v1.34.6+k3s1`, ma il preflight conferma ancora i cinque Secret e `mqtt-ca` assenti: nessun apply eseguito. Il tentativo di preparazione MQTT sulla VM si è fermato nel controllo iniziale di `ot.conf`, prima di modificare broker o credenziali.

Il successivo output della VM identifica una quarta direttiva `persistence` in `ot.conf`. Lo script di preparazione ora accetta un singolo booleano valido, conservando integralmente il file, il valore e la precedenza delle impostazioni. La correzione supera 25 test mirati e il collaudo Mosquitto reale in Docker, compresa la creazione del database di persistenza durante il riavvio. La preparazione sulla VM e il nuovo deploy restano da eseguire.

```text
Simulatore ── MQTT TLS/QoS1 ── broker esterno :8883
                                ├─ audit Python (metadati)
                                ├─ IA Python ── topic anomaly ─┐
                                └─ Node-RED <──────────────────┘
                                     │ token write sul bucket
                                     ▼
                                  InfluxDB
                                     ▲ token read sul bucket
                                     │
                                  Grafana
```

Il laboratorio rileva anomalie su singole letture simulate. Non controlla attuatori e non certifica la sicurezza di un processo industriale. OpenPLC è un componente opzionale isolato; non c'è un programma PLC né una sorgente Modbus collegata al simulatore.

## Componenti effettivi

| Percorso | Comportamento |
|---|---|
| `main.py` | Consumer audit: registra topic, dimensione e QoS, senza payload o credenziali |
| `IA-integration/raspi-simulator/` | Pubblica temperatura e umidità, incluse letture anomale simulate |
| `IA-integration/ia-consumer/` | Training riproducibile, verifica modello, inferenza e allarmi con ID deterministico |
| `platform/nodered/` | Nodo e flusso versionati: MQTT → validazione → scrittura InfluxDB → PUBACK |
| `platform/grafana/` | Datasource Flux `ot-influxdb`, dashboard `ot-security`, cinque pannelli dati e pannello descrittivo |
| `k3s/` | Sei deployment singleton, PVC, servizi interni e NetworkPolicy |
| `scripts/` | Bootstrap, token limitati, preflight, renderer e collaudo Docker completo |

Grafana visualizza temperatura, umidità, conteggio degli allarmi nell'intervallo scelto, timestamp dell'ultima lettura per sensore e tabella eventi. Nessun dato non equivale a un sensore sano. Flussi e dashboard sono gestiti dal repository: le modifiche passano da revisione, test e rilascio. L'editor Node-RED richiede login e il runtime è in modalità `readOnly`.

Il runtime Node-RED non contiene il gestore npm incorporato: l'override nel lockfile usa il pacchetto locale [disabled-npm](platform/nodered/runtime/disabled-npm/README.md), identificato con il proprio nome e senza dipendenze. Questo conserva la risoluzione dei percorsi richiesta all'avvio da Node-RED e rifiuta qualsiasi comando. L'aggiunta di nodi richiede una nuova build; gli strumenti di build continuano a usare npm reale. Il Dockerfile copia anche l'adattatore e rimuove npm globale dall'immagine finale.

## Contratto e consegna

Topic: `lab/raspi1/temperature` (`C`), `lab/raspi1/humidity` (`%`), `lab/raspi1/anomaly` (risultato IA con topic originale).

```json
{"device":"raspi1","ts":1760000000,"value":25.4,"unit":"C","in_range":true,"alert":null}
```

Payload JSON UTF-8 fino a 16 KiB: `device` contiene 1–128 lettere ASCII, cifre o `_.:-`; `ts` è un intero Unix in secondi da 0 a 9223372036; `value` è finito; l'unità corrisponde al topic. `in_range` è booleano opzionale, `alert` stringa su una riga fino a 128 caratteri o null. IA e Node-RED scartano messaggi invalidi con un log senza payload. Non modificare topic di un solo componente: il contratto è condiviso con i flussi e il dashboard.

L'IA normalizza i messaggi ai soli campi del contratto prima di calcolare `event_id` e costruire l'allarme. Le estensioni sconosciute sono ignorate: non possono causare errori di serializzazione o gonfiare l'uscita oltre il limite Node-RED. L'identificativo dipende dai campi normalizzati; messaggi che differiscono solo per estensioni hanno lo stesso ID. Il limite di `alert` conta punti di codice Unicode sia in Python sia in JavaScript.

MQTT usa TLS verificato, minimo 1.2, QoS1 e sessioni persistenti. Ogni ruolo ha ClientId stabile distinto. I deployment `Recreate` evitano sovrapposizioni: non aumentare le repliche senza riprogettare sessioni e distribuzione del carico. Il broker deve mantenere la persistenza e code dimensionate per i guasti previsti.

L'IA conferma l'ingresso dopo l'elaborazione e, per gli allarmi, dopo il PUBACK del broker. Node-RED conferma solo dopo HTTP 204 di InfluxDB. Durante un errore DB ritenta con backoff; una disconnessione annulla il tentativo della vecchia connessione, lasciando la riconsegna al broker. I messaggi malformati sono confermati e scartati per non bloccare la coda. QoS1 può duplicare consegne: InfluxDB usa measurement/tag/timestamp per riscrivere lo stesso punto. Due letture dello stesso sensore/tipo nello stesso secondo **si sovrascrivono**: il contratto attuale è per sensori a bassa frequenza. `event_id` resta un campo, non un tag ad alta cardinalità.

Non c'è garanzia contro perdita del disco del broker o della persistenza MQTT. La readiness Node-RED richiede connessione, sottoscrizioni e almeno una scrittura riuscita; non è un controllo di freschezza continuo. La dashboard espone il timestamp per individuare una sorgente ferma. I client non hanno liveness dipendente dal broker, per evitare riavvii collettivi durante un guasto.

Un singolo punto rifiutato definitivamente da InfluxDB con HTTP 413/422, o con HTTP 400 accompagnato dall'errore di parsing `invalid` / `unable to parse`, è confermato e scartato con log e incremento del contatore `rejected`, per non bloccare tutte le letture successive. Gli altri errori HTTP 400, di autenticazione/configurazione, rate limiting, rete e indisponibilità del DB mantengono il retry senza ACK: non vengono trattati come dati da scartare.

## Secret: riferimenti conservati e aggiunte approvate

Nessun valore segreto è incluso. Preparare file `nome-secret.env` con righe `KEY=value`, senza apici shell, in directory protetta esterna al checkout. Non inviare valori in chat. I nomi seguenti sono quelli letti dai manifest:

| Secret | Chiavi | Uso |
|---|---|---|
| `mqtt-credentials` | `username`, `password` | Riferimento originale del consumer audit |
| `observability-secrets` | `INFLUXDB_ADMIN_USER`, `INFLUXDB_ADMIN_PASSWORD`, `INFLUXDB_ADMIN_TOKEN`, `INFLUXDB_ORG`, `INFLUXDB_BUCKET`, `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD` | Riferimento originale, bootstrap DB e amministrazione Grafana |
| `mqtt-raspi-simulator` | `username`, `password` | Nuovo account producer |
| `mqtt-ia-consumer` | `username`, `password` | Nuovo account IA |
| `mqtt-nodered` | `username`, `password` | Nuovo account lettore MQTT |
| `nodered-auth` | `NODE_RED_ADMIN_USER`, `NODE_RED_ADMIN_PASSWORD_HASH`, `NODE_RED_CREDENTIAL_SECRET`, `INFLUXDB_WRITE_TOKEN` | Nuovi login bcrypt, cifratura stabile e token solo scrittura |
| `grafana-influxdb` | `INFLUXDB_READ_TOKEN` | Nuovo token solo lettura |

La CI legge i Secret GitHub `WG_CLIENT_PRIVATE_KEY`, `WG_SERVER_PUBLIC_KEY` e `K3S_KUBECONFIG`. L'endpoint pubblico non è una credenziale: `WG_ENDPOINT` è ora configurato nel workflow come `k3s--lab.cloud-ip.cc:51820`; il vecchio Secret omonimo non viene più letto e può rimanere salvato. Non serve un nuovo `WG_CLIENT_CONFIG`.

La CI adatta esclusivamente la copia temporanea del kubeconfig nel runner: imposta il server del contesto attivo a `https://192.168.1.21:6443`, rimuove un eventuale `tls-server-name` precedente e conserva CA, credenziali e altri contesti. Funziona anche con il Secret già salvato con server DDNS o localhost; il Secret GitHub non viene riscritto. Kubeconfig con verifica TLS disabilitata o proxy vengono rifiutati. Non viene modificato `/etc/hosts`. Il certificato K3s deve essere valido per l'IP **192.168.1.21**; il SAN DNS del DDNS non è richiesto. Per uso manuale, impostare lo stesso endpoint privato nel proprio kubeconfig. Verifica TLS e troubleshooting: [docs/K3S-TLS.md](docs/K3S-TLS.md).

Le build Grafana/InfluxDB usano anche `DOCKERHUB_USERNAME` e `DOCKERHUB_TOKEN` (PAT con sola lettura), confermati dal proprietario: autenticazione a `dhi.io` limitata ai runner di build. Le sei immagini finali sono pubblicate su GHCR; il cluster non riceve il PAT Docker Hub. Base64 nei Secret Kubernetes non è cifratura: RBAC, backup e cifratura at rest dipendono dal cluster.

## Preparazione del broker esterno

Usare `config/mosquitto.conf.example` e `config/mosquitto.acl.example` come riferimenti per il broker esistente. Creare i quattro account con `mosquitto_passwd` interattivo; adattare gli username nelle ACL ai valori già usati, senza rinominare le credenziali audit esistenti. Producer scrive solo temperatura/umidità; IA legge questi topic e scrive anomaly; Node-RED legge i tre topic; audit legge `lab/#`.

Il certificato deve avere **IP SAN 192.168.1.21** e una CA attendibile. Chiave privata solo sul broker. Distribuire la CA pubblica nel ConfigMap `mqtt-ca`, chiave `ca.crt`. Verificare senza disabilitare TLS:

```bash
openssl s_client -connect 192.168.1.21:8883 -CAfile ca.crt -verify_ip 192.168.1.21 -verify_return_error
```

Chiudere 1883 dopo aver migrato tutti i client. Il plaintext è ammesso solo nei test isolati con entrambe `MQTT_TLS=false` e `MQTT_ALLOW_INSECURE_LOCAL=true`; i manifest non lo abilitano.

## Bootstrap e rilascio K3s — da eseguire nel collaudo della VM

Prima di un aggiornamento salvare PVC, database e credenziali. Le immagini passano a Node-RED 5.0.7, Grafana 13.2.2 e InfluxDB 2.9.1: provare la migrazione su copie dei dati. InfluxDB 2.9 memorizza hash dei token; conservarne i valori nel gestore segreti prima dell'upgrade. Un semplice rollback dell'immagine non equivale a ripristinare il database. Il PVC `influxdb-config-pvc` conserva anche la configurazione CLI: includerlo nei backup e limitarne l'accesso.

Servono nodi Linux/amd64 Ready, storage class, immagini GHCR accessibili, CA, broker TLS e kubeconfig verificato per `https://192.168.1.21:6443` attraverso la VPN o la LAN. Se GHCR è privato configurare credenziali registry sui nodi o imagePullSecret prima del rollout. Il preflight richiede anche il permesso RBAC di leggere i nodi.

Il preflight raccoglie i Secret/ConfigMap mancanti, le chiavi assenti o vuote e gli errori di accesso senza stampare valori segreti. Un errore `NotFound` riguarda la preparazione delle risorse; `Forbidden` richiede la verifica dei permessi dell'identità del runner. I Secret applicativi vanno creati in Kubernetes e non tra i Secret GitHub. Per l'installazione esistente, seguire prima la [verifica del broker e delle credenziali](docs/K3S-SECRETS.md).

```bash
export SECRET_DIR='/percorso/protetto/segreti-lab'
export MQTT_CA_FILE='/percorso/ca.crt'
export RELEASE_SHA='<SHA completo già pubblicato dalla CI>'
bash scripts/bootstrap.sh
```

Lo script preserva i Secret già esistenti e crea solo quelli mancanti. InfluxDB usa l'immagine DHI 2.9.1, con percorsi dati e UID conservati. `initialize_influx.py` esegue il setup via API soltanto se il DB è vuoto; su un DB esistente verifica credenziali e bucket senza reinizializzare o ruotare token. Le vecchie variabili `DOCKER_INFLUXDB_INIT_*` non sono più necessarie al runtime. Non riutilizzare PVC con permessi incompatibili senza una migrazione esplicita: i processi applicativi girano senza root (UID 10001 Python, 1000 Node-RED/InfluxDB, 472 Grafana).

Aprire un port-forward locale a InfluxDB. In un secondo terminale impostare `INFLUXDB_URL=http://127.0.0.1:8086`, `INFLUXDB_ADMIN_TOKEN`, `INFLUXDB_ORG`, `INFLUXDB_BUCKET` tramite il proprio gestore di segreti:

```bash
kubectl -n ot-namespace port-forward service/influxdb 8086:8086 --address=127.0.0.1
# Secondo terminale, dal repository:
python scripts/provision_influx_tokens.py --output "$SECRET_DIR"
```

Lo script crea token limitati al solo bucket e scrive `influx-write.env` e `grafana-influxdb.env` senza stamparli; rifiuta overwrite e directory dentro il repository. Su Windows proteggere la directory con ACL dell'account. Integrare la riga `INFLUXDB_WRITE_TOKEN` nel file `nodered-auth.env`, insieme all'utente, hash bcrypt (`node-red admin hash-pw`) e chiave di cifratura casuale stabile. Conservare quest'ultima con i backup. Quindi:

```bash
kubectl -n ot-namespace create secret generic nodered-auth --from-env-file="$SECRET_DIR/nodered-auth.env"
kubectl -n ot-namespace create secret generic grafana-influxdb --from-env-file="$SECRET_DIR/grafana-influxdb.env"
python scripts/render_release.py "$RELEASE_SHA" --output rendered
python scripts/preflight.py rendered
kubectl apply --dry-run=server -f rendered
kubectl apply -f rendered
for app in influxdb nodered grafana ot-mqtt-consumer raspi-simulator ia-consumer; do
  kubectl -n ot-namespace rollout status deployment/$app --timeout=360s
done
python scripts/postdeploy_check.py
```

Usare lo SHA completo di una release pubblicata con CI verde. Il renderer genera anche i tre ConfigMap Grafana e la checksum di provisioning; non modifica i sorgenti. Non applicare direttamente `k3s/`, che contiene tag `RELEASE_SHA`. I sei tag di rilascio sono `<sha>`, `raspi-simulator-<sha>`, `ia-consumer-<sha>`, `nodered-<sha>`, `grafana-<sha>` e `influxdb-<sha>`. Dopo rotazione dei Secret riavviare consapevolmente i pod interessati.

Accesso alle UI tramite port-forward su localhost; login con i rispettivi account:

```bash
kubectl -n ot-namespace port-forward service/grafana 3000:3000 --address=127.0.0.1
kubectl -n ot-namespace port-forward service/nodered 1880:1880 --address=127.0.0.1
```

Grafana: `http://127.0.0.1:3000/d/ot-security`. Le NetworkPolicy limitano InfluxDB a Node-RED/Grafana e le UI ai pod amministrativi etichettati; verificare enforcement K3s. Non pubblicare questi HTTP interni su internet. Per un accesso remoto diretto usare un reverse proxy TLS autenticato; il traffico interno HTTP assume una rete del cluster attendibile. Gli endpoint di amministrazione InfluxDB sono raggiunti dall'operatore tramite port-forward.

OpenPLC in `k3s/optional/` è fissato a digest e protetto da policy separata. La porta 8443 serve l'API dell'Editor v4, non una UI web; Modbus 502 richiede un programma/configurazione adeguati. Capability realtime e storage vanno collaudati a parte. Non viene avviato dal percorso core né collegato ad attuatori. Applicare entrambi i file opzionali solo quando viene introdotto quel collaudo.

## Verifiche riproducibili

Python 3.11, Node.js 24, Docker Linux e OpenSSL per il test completo:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
export PYTHONPATH="$PWD"
bash scripts/run_tests.sh
bash scripts/run_sast.sh
npm ci --ignore-scripts --prefix platform/nodered
npm test --prefix platform/nodered
npm audit --omit=dev --audit-level=high --prefix platform/nodered
bash scripts/validate_config.sh
(cd IA-integration/ia-consumer && python train_model.py)
```

Per provare l'intero stack senza il cluster, autenticarsi a `dhi.io` con `docker login dhi.io` usando un PAT con sola lettura, costruire le sei immagini con lo stesso SHA e lanciare:

```bash
export RELEASE_SHA="$(git rev-parse HEAD)"
export IMAGE_NAME=ghcr.io/davidevaloroso-sys/ot-security
docker build -t "$IMAGE_NAME:$RELEASE_SHA" .
docker build -f IA-integration/raspi-simulator/Dockerfile -t "$IMAGE_NAME:raspi-simulator-$RELEASE_SHA" .
docker build -f IA-integration/ia-consumer/Dockerfile -t "$IMAGE_NAME:ia-consumer-$RELEASE_SHA" .
docker build -f platform/nodered/Dockerfile -t "$IMAGE_NAME:nodered-$RELEASE_SHA" .
docker build -f platform/grafana/Dockerfile -t "$IMAGE_NAME:grafana-$RELEASE_SHA" .
docker build -f platform/influxdb/Dockerfile -t "$IMAGE_NAME:influxdb-$RELEASE_SHA" .
python scripts/integration_test.py "$RELEASE_SHA"
```

Il test genera credenziali e certificati temporanei, usa porte casuali su localhost e una rete Docker dedicata. Prova MQTT TLS, inferenza, scrittura reale InfluxDB, token con permessi minimi, autenticazione Node-RED, datasource e ogni query della dashboard Grafana, poi arresto/ripristino del DB. Rimuove esclusivamente i propri container e volumi temporanei. Non usa il broker `192.168.1.21`. Richiede un Docker daemon funzionante; un test saltato non è un test superato.

Le verifiche di persistenza risolvono la porta pubblicata corrente di InfluxDB anche dopo un riavvio e controllano record CSV effettivi. Le pubblicazioni di test richiedono il PUBACK del broker; un timeout di pubblicazione viene riportato separatamente dal mancato salvataggio nel DB.

Lo smoke aggiuntivo `platform/nodered/test/runtime.cjs`, con `NODE_RED_RUNTIME` impostato al `red.js` installato, avvia Node-RED reale con broker e server HTTP di test. Non sostituisce il collaudo InfluxDB/Grafana.

## CI e qualità del modello

Le PR e i push a main eseguono test, Bandit, validazione schema, training, sei build e Trivy HIGH/CRITICAL; nessuna pubblicazione precede scansioni e integrazione. Solo main pubblica le immagini già provate. Modifiche limitate a README e `docs/` non avviano una nuova release. Actions e basi container sono fissate; Dependabot aggiorna Python, Docker, npm e Actions. La scansione può bloccare anche dipendenze upstream senza fix: non ignorare automaticamente gli avvisi.

Grafana viene costruita dalla base DHI 13.2.2 con il solo plugin InfluxDB 13.1.6, verificato tramite checksum e caricato da un percorso nell'immagine. Installazione automatica dei plugin e aggiornamenti sono disabilitati; il PVC non sostituisce il plugin scansionato. La scansione della candidata è integrata con l'SBOM SPDX firmato della base, preservato in `platform/grafana/security/`: aggiornare base e inventario insieme, seguendo [la procedura](docs/GRAFANA-SBOM.md).

Il deploy usa i Secret WireGuard originali e l'environment `lab`, rifiuta revisioni superate e nodi incompatibili, attende i sei rollout e lancia `postdeploy_check.py`. Quest'ultimo apre port-forward localhost temporanei e verifica salute dei servizi, datasource, corrispondenza delle query della dashboard alla release e letture temperatura/umidità persistite negli ultimi cinque minuti. Non crea allarmi o guasti sul laboratorio: le prove di interruzione avvengono nello stack Docker isolato.

Il runner installa `kubectl v1.34.6` dall'origine ufficiale verificandone SHA256, allineato al server osservato `v1.34.6+k3s1`. Il client preinstallato `v1.37.1` era oltre lo scarto supportato di una minor: aggiornare il pin insieme al cluster, secondo la [compatibilità Kubernetes](https://kubernetes.io/releases/version-skew-policy/#kubectl). Questa correzione non crea le credenziali mancanti.

Il training valida dati/classi/unità, fa split stratificato 80/20 con seed 42 e registra hash, versioni, soglia runtime 0.70 e metriche. Il runtime rifiuta un artefatto alterato o incompatibile. I gate di regressione del laboratorio richiedono precisione e recall della classe anomala almeno 0.95 anche quando le variabili CI sono assenti o vuote. `MIN_ANOMALY_RECALL` e `MIN_ANOMALY_PRECISION` consentono override espliciti, registrati nelle metriche. Questi limiti verificano la regressione sul dataset incluso, non sono obiettivi di sicurezza industriale: la release resta sperimentale. Servono dati indipendenti, verifica di drift e costi dei falsi allarmi prima di applicazioni reali. Caricare solo modelli joblib attendibili.

La proposta di hardening usa Python Alpine per audit/simulatore e InfluxDB 2.9.1 Alpine, mantenendo UID e versione applicativa. L'inferenza conserva la base precedente: scikit-learn 1.6.1 non fornisce wheel musllinux e richiede un percorso di build distinto prima di poter migrare. Le scansioni restano bloccanti, comprese le vulnerabilità nei binari Go upstream. Vedere `docs/REMEDIATION-STATUS.md` per prove effettuate e verifiche ancora necessarie.

## Collaudo sulla VM

Verificare versione K3s/storage, permessi PVC, broker TLS/ACL, disponibilità immagini e Secret con preflight. Eseguire dry-run server, rollout, accesso UI, letture normali/anomale e riscontro timestamp in Grafana. Provare CA e password errate, topic negati, perdita broker/DB, recupero e riconsegna. Verificare backup/ripristino e enforcement delle NetworkPolicy. Solo queste prove sul server possono attestare l'operatività del laboratorio reale.

Riferimenti: [Node-RED security](https://nodered.org/docs/user-guide/runtime/securing-node-red), [Grafana provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/), [InfluxDB scoped tokens](https://docs.influxdata.com/influxdb/v2/admin/tokens/create-token/), [InfluxDB upgrade](https://docs.influxdata.com/influxdb/v2/install/upgrade/v2-to-v2/), [OpenPLC Docker](https://github.com/Autonomy-Logic/openplc-runtime/blob/main/docs/DOCKER.md).
