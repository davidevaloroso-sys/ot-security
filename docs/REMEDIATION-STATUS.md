# Attività e risultati OT-Security — 29 settembre 2026

## Stato della release

Il proprietario ha autorizzato correzioni, push diretto a `main`, test e deploy K3s; ha confermato l'uso dei Secret GitHub WireGuard/Kubeconfig già configurati. Docker Desktop Linux è ora disponibile. Il PC non ha un contesto Kubernetes locale: il job GitHub nell'environment `lab` raggiunge la VM `192.168.1.21` tramite `k3s--lab.cloud-ip.cc`; la stessa VM ospita anche il broker MQTT.

La candidata locale ha completato i controlli riportati sotto. CI remota, pubblicazione e deploy di queste modifiche devono ancora essere verificati. Nessun risultato locale viene presentato come rollout sul laboratorio.

Il run remoto [36615805957](https://github.com/davidevaloroso-sys/ot-security/actions/runs/36615805957) sul commit `2189c19` ha superato test/training, sei build, scansioni, integrazione e pubblicazione delle immagini. Il job `deploy_k3s` ha validato il nome DDNS nel kubeconfig e la VPN, ma `kubectl get --raw=/version` è terminato dopo 30 secondi con `Client.Timeout exceeded while awaiting headers`, prima di qualsiasi dry-run o apply. Le verifiche sulla VM hanno poi mostrato K3s in ascolto su `*:6443` sull'host `192.168.1.21`, mentre il runner stava instradando l'API verso l'indirizzo errato `192.168.1.12`. Il commit locale successivo corregge `AllowedIPs` e la mappatura temporanea del DDNS verso `192.168.1.21`; anche il broker MQTT usa `.21`.

## Cronologia e correzioni

- Base iniziale analizzata: `0cb9d376d490579d7110350305967920433a7251`.
- `60ac14165ce8180119e851780d5a0f33cfb1a026`, già pubblicato su main: normalizzazione del contratto IA, rimozione delle estensioni arbitrarie, limite Unicode condiviso degli alert, distinzione fra errori permanenti e transitori di InfluxDB, controllo PUBACK, query di persistenza effettive e risoluzione delle porte dopo riavvio. Gate di regressione training 0.95 per precisione/recall anomalia, con override espliciti registrati.
- `82184140b9826a46d177068d5bcb1282d05beea1`: aggiornamento documentazione. La [CI di questo SHA](https://github.com/davidevaloroso-sys/ot-security/actions/runs/36506146251) aveva superato test, quattro build e integrazione, ma falliva lo scanner; publish/deploy erano saltati.
- Il job attuale ha sostituito la base Debian IA con Alpine in due stadi. scikit-learn 1.6.1 viene compilato con due processi; versioni runtime invariate, compilatori e installer esclusi dall'immagine finale. Nessuna modifica al formato del modello.
- InfluxDB passa a DHI 2.9.1, conservando UID 1000 e percorsi del PVC. Il setup viene eseguito tramite API da `initialize_influx.py`, solo se il database è vuoto; un DB esistente viene verificato senza reset o rotazione implicita. Bootstrap e integrazione sono stati aggiornati.
- Grafana passa a una build del progetto basata su DHI 13.2.2 con il solo plugin InfluxDB 13.1.6, archivio ufficiale fissato tramite SHA256. Plugin fuori dal PVC, root filesystem in sola lettura, installazioni automatiche disabilitate. La pipeline ora costruisce, prova, scansiona e pubblica sei immagini.
- La scansione della base Grafana è completata con l'SPDX upstream, firmato e verificato contro la chiave Docker. Hash, digest immagine/piattaforma e attestazione sono registrati; il gate rifiuta una base aggiornata senza inventario corrispondente. Nessuna esclusione CVE/VEX aggiunta. Dettagli in [GRAFANA-SBOM.md](GRAFANA-SBOM.md).
- Deploy abilitato su push main, subordinato a tutti i gate, con timeout, controllo configurazione VPN, verifica endpoint TLS, nodi Linux/amd64 Ready e controllo SHA prima dell'apply. Rollout 360s, coerente con startup probe 300s.
- `postdeploy_check.py` aggiunge verifica di salute Node-RED/InfluxDB/Grafana, datasource, corrispondenza delle query provisionate e dati reali temperatura/umidità degli ultimi 5min. Port-forward temporanei localhost e credenziali in memoria; niente stampa di valori segreti.
- Corrette incoerenze documentali: Docker disponibile, deploy autorizzato, sei tag di release, inizializzazione Influx via API, tag versionati per commit invece di garanzia impropria di immutabilità. Le sole modifiche README/docs non creano nuove release.

## Controlli locali conclusi

| Verifica | Esito |
|---|---|
| Pytest, ambiente Python 3.12.14 | 94 test passati |
| Cinque build Docker Linux | Passate; Python runtime 3.11.16 |
| Caricamento modello IA, UID 10001, filesystem read-only, rete assente | Passato |
| Portabilità modello su 10.000 righe | Differenza massima probabilità 0.0, classi identiche a soglia 0.70 |
| Trivy 0.74.0, sei candidate e Influx DHI | Zero HIGH/CRITICAL; scansione vulnerabilità e segreti |
| SPDX base Grafana, 550 componenti più radice | Firma verificata; zero HIGH/CRITICAL con Trivy |
| Integrazione Docker reale | TLS MQTT, IA, persistenza, token read/write limitati, login Node-RED, datasource, cinque query Grafana e outage/recovery DB superati |
| actionlint 1.7.7, kubeconform 0.6.7, schema Kubernetes 1.31 | Workflow valido; 25 risorse valide, zero errori |
| Rendering e preflight offline | Passati; non attestano lo stato dei Secret del cluster |
| Bandit Medium+ / confidenza Medium+ | Passato su applicazioni e nuovi script operativi |

I test Node-RED (28), il runtime reale e il training erano già passati nella CI precedente; la nuova CI li riesegue. Il training usa Python 3.11, split stratificato 8000/2000, seed42, precisione/recall anomalia 1.0 sul dataset incluso. Queste metriche non qualificano un impianto industriale reale.

## Problemi incontrati e risolti durante il job

1. Il primo accesso Docker era negato dal sandbox; l'accesso autorizzato al daemon dell'utente ha confermato Docker Desktop attivo.
2. Influx DHI non include l'entrypoint di setup della vecchia immagine. Introdotto setup API idempotente e collaudato che il secondo passaggio non reinizializzi il DB.
3. Docker non applica `fsGroup` come Kubernetes: il test crea un volume proprio e imposta UID 1000 prima dell'avvio; il volume persiste nel test di riavvio e viene rimosso solo dal cleanup dello stack temporaneo.
4. Grafana DHI scaricava plugin all'avvio: sostituito il comportamento con plugin preinstallato, fisso e scansionato. Verificata l'esecuzione delle query reali, non solo `/api/health`.
5. Il formato CycloneDX del fornitore perdeva lo scope `@types` di js-cookie, causando un falso positivo. Usato il distinto formato SPDX firmato, che conserva l'identità del package, senza alterare inventari o ignorare CVE.
6. La verifica firma iniziale falliva per assenza dell'attestazione in Rekor: usata la modalità Docker documentata `--verify --skip-tlog`, mantenendo la verifica crittografica della firma e dei claims. La vecchia Docker Scout 1.20.2 ha inoltre un crash nel percorso VEX; nessun VEX è stato necessario o usato nel gate.
7. Il collaudo era terminato funzionalmente ma la stampa Unicode falliva nella console Windows cp1252. Il messaggio finale ora usa ASCII e il test è stato rieseguito con exit 0.

## Evidenze e limiti

Report locali ignorati da Git in `test-results/`: `local-security.json`, `raspi-simulator-local-security.json`, `ia-alpine-security.json`, `nodered-local-security.json`, `grafana-local-security.json`, `influx-final-security.json`, `grafana-spdx-security.json`. L'inventario di sicurezza della base è invece versionato nel repository per essere scansionato dalla CI.

Restano da registrare lo SHA pubblicato, l'esito della nuova CI, il preflight online, l'eventuale rollout e lo smoke del laboratorio. Backup/ripristino dei dati reali, enforcement NetworkPolicy e prove di guasto sul cluster non sono stati eseguiti da questo collaudo locale; non vengono dichiarati superati. Non eliminare PVC o resettare credenziali per superare un errore di avvio.


## Ripresa dopo la configurazione dei Secret Docker Hub

La [CI del commit fb0ce69](https://github.com/davidevaloroso-sys/ot-security/actions/runs/36556583531) ha superato test/training e tutte le cinque build allora previste. Scansioni applicative e inventario Grafana sono passati; integrazione e scansione core si sono fermate perché il runner non poteva scaricare InfluxDB da dhi.io (HTTP 401). Pubblicazione e deploy non sono avvenuti.

Il proprietario ha creato e confermato `DOCKERHUB_USERNAME` e `DOCKERHUB_TOKEN`. La correzione autentica soltanto le build DHI e include InfluxDB come sesta immagine del progetto: scansione, integrazione e cluster usano gli stessi artefatti GHCR, senza distribuire il PAT Docker Hub. Il bootstrap ora richiede RELEASE_SHA e applica il manifest InfluxDB renderizzato. README e checklist sono stati allineati.

Sono stati corretti anche gli avvisi npm risolvibili: UUID 11.1.1 nei test, Multer 2.4.0 e ip-address 10.7.2 nel runtime, con lockfile aggiornati. I 28 test Node-RED e lo smoke del runtime reale sono passati. L'audit del nodo custom è a zero; il runtime mantiene due avvisi moderati nei package ip-address 10.5.0 e undici 6.28.0 incorporati da npm 11.19.1, dipendenza di @node-red/registry. Gli override npm non sostituiscono questi bundle. Anche le versioni npm 11.20.0 e 12.1.0 controllate conservano i bundle vulnerabili: gli aggiornamenti sperimentali non sono stati adottati. Il gestore di installazione moduli è disabilitato dalla configurazione del prodotto; gli avvisi restano registrati, senza esclusioni o dichiarazioni di risoluzione.
