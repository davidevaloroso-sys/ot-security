# Attività e risultati OT-Security — 29–30 settembre 2026

## Stato della release

**Concluso: deploy e smoke K3s superati il 30 settembre alle 18:48:53 CEST.** Release `0f98845c92ba2e6471a96d50159f82546d071d47`, [run 36744724064](https://github.com/davidevaloroso-sys/ot-security/actions/runs/36744724064), tutti i job verdi. I due Secret osservabilità sono stati creati, sei rollout completati, salute/datasource/cinque query e dati recenti di temperatura/umidità verificati sul cluster. [Report finale](DEPLOYMENT-2026-09-30.md).

La revisione dopo il deploy ha confrontato endpoint MQTT/TLS, riferimenti dei manifest, renderer e controlli delle query. Nessuna ulteriore incoerenza funzionale emersa; aggiornato il README eliminando stato operativo obsoleto e descrizione errata della base IA. Le sezioni seguenti sono **cronologia dei tentativi**, con i blocchi e gli esiti noti in quel momento; non descrivono lo stato attuale.

### Audit npm dopo il push 15fc489

Verificato l'ultimo tentativo del run `36743791003`, job `109985384502`: errore in `Validate locked Node-RED runtime`, prima del training e delle build. Il conteggio npm di otto voci (una HIGH, sette MODERATE) comprende i pacchetti che dipendono da `axios 1.19.0` e `moment 2.30.1`; il nodo custom OT aveva audit zero. Nessun deploy è stato tentato da questo run.

Fissati override `axios 1.20.0` e `moment 2.31.0`, con lockfile rigenerato da npm: cambiano soltanto versione, URL e integrità di questi due pacchetti. Versioni corrette confermate dagli advisory upstream [Axios](https://github.com/advisories/GHSA-542g-h47m-68v8) e [Moment](https://github.com/advisories/GHSA-4p3w-j4w9-5jqw). Nessuna esclusione o modifica della soglia dell'audit. Installazione pulita Linux Node 24 e audit del runtime: zero vulnerabilità. Smoke Node-RED reale passato: flusso caricato, login obbligatorio, installazione runtime negata e persistenza dell'ingresso MQTT.

Immagine Docker ricostruita `ot-security-nodered:axios-moment-fix`, manifest `sha256:1328102dd46fcf4838d155d4dc57227c1782f717426aa368ce3f902ff0176e06`; confermate le versioni dei due pacchetti anche dall'interno del container. Trivy 0.74.0 con database aggiornato: zero HIGH/CRITICAL e zero segreti, exit 0. Report locale ignorato da Git in `test-results/nodered-axios-moment-security.json`. Il deploy resta da confermare nella nuova pipeline.

### Deploy 36740613024: preparazione automatica dei due Secret residui

Confermato dall'output del proprietario il completamento della migrazione MQTT sulla VM: TLS/IP SAN, quattro login, account originale 1883 e creazione dei tre Secret MQTT e della CA. La CI del commit `5dbf97a` ha superato test/training, sei build, scansioni, integrazione e publish. Il job deploy `109979703753` si è fermato prima dell'apply: `NotFound` soltanto per `grafana-influxdb` e `nodered-auth`.

Introdotta preparazione automatica prima del preflight, con controllo SHA: usa le credenziali InfluxDB originali per verificare org/bucket esistenti ed emettere due token limitati. Crea solo Secret assenti, preserva quelli presenti e rifiuta quelli incompleti. Recupera la chiave automatica Node-RED se disponibile; configurazioni esplicite/ambigue fermano la procedura. Login nuovo `ot-admin`, hash bcrypt e password di recupero conservati nel Secret; valori mai nei log. Nessun reset DB, modifica PVC o riscrittura dei flussi precedenti durante la preparazione.

17 test mirati passati; Bandit Medium/High senza risultati. Collaudo Docker reale passato con InfluxDB 2.9.1 e Node-RED: token read/write con accessi opposti negati, chiave legacy conservata, bcrypt, nessuna modifica al secondo passaggio, configurazioni di cifratura ambigue rifiutate. Il test ha confermato che InfluxDB 2.9 non restituisce nuovamente i token: un errore fra emissione e creazione Secret richiede intervento e non provoca duplicati automatici. Kubernetes è simulato in questo collaudo; l'esito della nuova pipeline e il rollout restano da verificare.

### Correzione della migrazione dopo l'ispezione di ot.conf

Il proprietario ha confermato una quarta direttiva `persistence` in `ot.conf`; il valore è stato oscurato nell'output diagnostico. Il controllo troppo rigido rifiutava il file prima di qualsiasi scrittura. Lo script ora ammette una singola direttiva `persistence true` o `persistence false`, lasciando il file integro e senza spostare l'impostazione rispetto al file principale. Restano rifiutati valori invalidi, duplicati, listener/password file alternativi, plugin e modifiche all'autenticazione.

Verifica: 25 test mirati passati. Collaudo in container temporaneo con Mosquitto reale passato: configurazione legacy con persistenza abilitata, database creato durante il riavvio, conservazione byte per byte di `ot.conf` e del password file, TLS e quattro login, account originale sulla 1883, rifiuto di password/IP errati, permessi privati e protezione dalle riesecuzioni. Kubernetes e il gestore del servizio sono simulati nel test; questo esito non attesta ancora la migrazione sulla VM.

### Verifica del 30 settembre, ripresa delle 09:00 CEST

La [CI 36658383049](https://github.com/davidevaloroso-sys/ot-security/actions/runs/36658383049), commit `efb17b548943c2c1936c89b3a52c6582db7de841`, ha superato test/training, sei build, security scan, integration e publish. Il job `deploy_k3s` (`109710601125`) ha raggiunto l'API K3s `v1.34.6+k3s1`; si è fermato prima dell'apply per risorse assenti in `ot-namespace`: Secret `grafana-influxdb`, `mqtt-ia-consumer`, `mqtt-nodered`, `mqtt-raspi-simulator`, `nodered-auth` e ConfigMap `mqtt-ca`. Il log classifica tutti i casi come `NotFound`; non indica un errore di apply o di permessi.

Il proprietario ha scaricato e verificato tramite SHA256 `prepare_mqtt_tls.py` dal commit `c552cb0`, quindi eseguito `--apply`. La procedura è terminata con `Legacy ot.conf differs from the inspected three-line configuration`, durante i controlli iniziali e prima delle mutazioni. Il precedente grep mostrava solo alcune direttive e non provava che il file ne contenesse esattamente tre. Richiesto un inventario filtrato delle direttive di `ot.conf`, senza valori di credenziali, per distinguere differenze di formattazione da configurazioni aggiuntive. Non è stato indebolito il controllo né rilanciato un deploy destinato a fallire sullo stesso prerequisito.

Aggiornamento inviato alla conversazione cloud del report. Rollout e collaudo sul cluster restano da completare; i workload precedenti non attestano la nuova release.

### Blocco npm rilevato e corretto il 30 settembre

Il commit `c552cb0` è stato pubblicato direttamente su main con diagnostica del preflight, client kubectl compatibile e procedura MQTT. La [CI 36657062263](https://github.com/davidevaloroso-sys/ot-security/actions/runs/36657062263) si è fermata in `Validate locked Node-RED runtime`: `undici 6.28.0` incluso in `npm 11.19.1` risulta HIGH; build, publish e deploy saltati. I precedenti override non sostituivano i package incorporati. Le release npm 11.20.0/12.1.0 verificate contengono ancora i bundle vulnerabili.

Il runtime del prodotto aveva già palette, upload e auto-install disabilitati. La correzione elimina completamente il gestore npm incorporato e i suoi 143 package bundled: 144 voci rimosse dal lockfile, nessuna riscrittura delle versioni installate o esclusione CVE. Un pacchetto locale esplicito `@ot-security/disabled-npm` permette soltanto la risoluzione del percorso `npm/package.json` richiesta da Node-RED all'avvio; ogni comando, incluse le richieste di versione, termina con errore senza echo di argomenti o variabili. npm reale rimane uno strumento di build, rimosso dall'immagine finale come prima. Due dipendenze di soli tipi TypeScript hanno ricevuto patch durante la rigenerazione del lockfile.

Verificati installazione pulita con `npm ci`, audit con zero vulnerabilità e smoke Node-RED reale: avvio flusso versionato, login amministrativo, scrittura MQTT e rifiuto dell'installazione di moduli anche con autenticazione amministrativa. L'immagine Docker corretta è stata costruita localmente. Il gate HIGH/CRITICAL della pipeline resta invariato.

La prima build usava un symlink per il pacchetto locale: Trivy ricostruiva ancora i vecchi package npm dello strato di base, sebbene quei file fossero assenti nel filesystem effettivo del container (digest confrontati). Abilitato `install-links=true` nel progetto runtime e rigenerato il lockfile, così l'adattatore viene installato come directory reale anche in CI e nell'immagine. Ripetuti installazione pulita, audit e smoke con esito positivo. Trivy 0.74.0 con database aggiornato del 30 settembre sull'immagine `sha256:f8ca1ed76958054b44b4aad2a44ce46b5eb8e5bddc2524e9a1dd5b4a60af64f6`: **zero HIGH/CRITICAL e zero segreti rilevati**, exit 0. Report locale in `test-results/nodered-no-installer-security.json`.

Creato e verificato il report nella [conversazione cloud «Report — 30 settembre 2026»](https://chatgpt.com/c/6abc6b51-6920-83eb-b695-db0133a2b4cc), dentro il progetto OT-Security; viene aggiornato con gli esiti verificati, senza dichiarare un deploy non avvenuto.

### Ripresa del 30 settembre: preparazione MQTT

Il proprietario ha verificato Mosquitto attivo come servizio sulla VM, con autenticazione sulla sola porta 1883; nessun container Docker attivo. La configurazione rilevata usa `/etc/mosquitto/conf.d/ot.conf` e `/etc/mosquitto/passwd`. Il nuovo deploy richiede il listener TLS 8883: creare i Secret senza configurare il broker non sarebbe sufficiente.

Aggiunto `scripts/prepare_mqtt_tls.py`: controllo iniziale senza scritture, migrazione esplicita con `--apply`, conservazione di listener/password file precedenti, CA privata e IP SAN `.21`, quattro account TLS con ACL per ruolo, riavvio con ripristino configurazione in caso di errore, verifica login e creazione dei soli tre Secret MQTT mancanti e del ConfigMap CA. Backup e nuove credenziali restano protetti sulla VM; nessun valore nei log, negli argomenti dei processi o in Git. L'account audit originale non viene ruotato. Il nuovo script non viene eseguito automaticamente dalla CI e non è ancora stato applicato alla VM.

Colloquio con il broker collaudato in un container Linux temporaneo: controllo senza modifiche, migrazione, TLS, quattro login, conservazione del login sulla 1883, rifiuto password e IP SAN errati, permessi root/gruppo Mosquitto, risorse Kubernetes create una volta e blocco delle riesecuzioni. Kubernetes e systemctl sono simulati nel test; il broker, certificati e autenticazione sono reali. Il primo tentativo di test mancava dello stub systemctl nel container, corretto prima del collaudo riuscito. Suite locale: 138 test. Bandit comprende il nuovo script, con una sola eccezione B103 documentata per il bit di attraversamento della directory da parte del gruppo Mosquitto (0710, nessuna scrittura di gruppo o accesso agli altri).

Restano da applicare la preparazione MQTT sulla VM, creare i token e il Secret Node-RED per l'InfluxDB esistente, poi verificare preflight, rollout e postdeploy. Il client SSH locale non ha una chiave host conosciuta per `.21`; non è stato stabilito un accesso SSH al server. Il report richiesto va pubblicato nella conversazione cloud del progetto OT-Security, senza dichiarare il deploy completato.

Aggiornamento dopo il run [36628560125](https://github.com/davidevaloroso-sys/ot-security/actions/runs/36628560125), commit `b70bd07`: test/training, sei build, scansioni, integrazione e publish superati. Il runner raggiunge l'API con TLS verificato e riceve `v1.34.6+k3s1`. Il deploy fallisce leggendo `grafana-influxdb`, prima di dry-run/apply. Il traceback precedente nascondeva stderr: da solo non distingueva assenza e RBAC. L'inventario locale fornito dal proprietario conferma soltanto `mqtt-credentials` e `observability-secrets` fra i Secret e soltanto `kube-root-ca.crt` fra i ConfigMap. Mancano quindi cinque Secret applicativi e `mqtt-ca`; i sette deployment precedenti sono disponibili.

Correzione successiva: il preflight classifica gli errori senza stampare stdout/stderr, verifica tutte le risorse richieste e segnala anche le chiavi vuote. Nessuna credenziale viene creata o modificata. Aggiunta [procedura di verifica e preparazione](K3S-SECRETS.md); TLS/account del broker sono ancora da verificare sulla VM. Allineato inoltre il client CI a `kubectl v1.34.6`, con verifica del checksum ufficiale, perché quello preinstallato `v1.37.1` superava lo scarto supportato dal server.

Validazione locale di questa correzione: 138 test Python superati, Bandit Medium+/confidenza Medium+ senza rilievi, actionlint e preflight offline superati, 25 risorse valide con kubeconform. Verificati download, SHA256 e avvio del client Linux `v1.34.6` in Docker con checkout in sola lettura. Il deploy resta da completare dopo il provisioning delle risorse reali del laboratorio.

Il proprietario ha autorizzato correzioni, push diretto a `main`, test e deploy K3s; ha confermato l'uso dei Secret GitHub WireGuard/Kubeconfig già configurati. Docker Desktop Linux è ora disponibile. Il PC non ha un contesto Kubernetes locale: il job GitHub nell'environment `lab` apre WireGuard tramite `k3s--lab.cloud-ip.cc:51820` e raggiunge l'API privata `192.168.1.21:6443`; la stessa VM ospita anche il broker MQTT.

Il [run remoto 36624149826](https://github.com/davidevaloroso-sys/ot-security/actions/runs/36624149826), sul commit `9435bf8`, ha superato test/training, sei build, scansioni, integrazione e publish. Il deploy si è fermato prima dell'apply con `x509: certificate is valid for ..., not k3s--lab.cloud-ip.cc`. Il proprietario ha chiarito che il DDNS serve solo alla VPN. La nuova configurazione elimina il nome DNS dall'API e mantiene la verifica TLS sull'IP privato; il nuovo rollout non è ancora confermato. Dettagli in [K3S-TLS.md](K3S-TLS.md).

La correzione usa l'endpoint pubblico esplicito nel workflow e non legge più il vecchio Secret `WG_ENDPOINT`. Conserva le chiavi WireGuard e il Secret `K3S_KUBECONFIG`: solo la copia del runner viene adattata al server privato, mantenendo CA/credenziali, togliendo l'override TLS DNS e rifiutando proxy o verifica TLS disabilitata. Nessuna modifica a `/etc/hosts`, alla CA o ai certificati della VM. Il preflight distingue ora la validazione della configurazione dalla successiva connessione reale. I test coprono endpoint errati, verifica TLS, proxy, selezione del contesto, conservazione credenziali e assenza di contenuti segreti negli errori.

Il run remoto [36615805957](https://github.com/davidevaloroso-sys/ot-security/actions/runs/36615805957) sul commit `2189c19` ha superato test/training, sei build, scansioni, integrazione e pubblicazione delle immagini. Il job `deploy_k3s` ha validato il nome DDNS nel kubeconfig e la VPN, ma `kubectl get --raw=/version` è terminato dopo 30 secondi con `Client.Timeout exceeded while awaiting headers`, prima di qualsiasi dry-run o apply. Le verifiche sulla VM hanno poi mostrato K3s in ascolto su `*:6443` sull'host `192.168.1.21`, mentre il runner stava instradando l'API verso l'indirizzo errato `192.168.1.12`. Il commit locale successivo corregge `AllowedIPs` e la mappatura temporanea del DDNS verso `192.168.1.21`; anche il broker MQTT usa `.21`.

Verifica locale della correzione DDNS/API: 110 test Python superati, Bandit senza risultati Medium/High, actionlint e preflight offline superati, kubeconform con 25 risorse valide e zero errori. La verifica Linux è stata eseguita in un container temporaneo con checkout in sola lettura; il primo tentativo richiedeva coreutils al posto dello sha256sum BusyBox, il secondo è terminato con successo. Questi controlli non attestano ancora un deploy sul cluster.

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
| Pytest, ambiente Python 3.12.14 | 138 test passati dopo la diagnosi degli errori del preflight |
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
