# Deploy OT-Security — 30 settembre 2026

**Esito: completato sul laboratorio K3s.** Release `0f98845c92ba2e6471a96d50159f82546d071d47`, [pipeline 36744724064](https://github.com/davidevaloroso-sys/ot-security/actions/runs/36744724064), tutti gli undici job conclusi con successo. Il job deploy `109993856069` termina il collaudo alle **18:48:53 CEST / 16:48:53 UTC**. Questa è la verifica del run, non una misura continua della disponibilità del cluster.

## Attività completate

- Corretti contratto telemetria, gestione errori e conferme MQTT, controlli di persistenza e test di regressione IA.
- Allineati i sei artefatti container, build riproducibili tramite lockfile, scansioni e integrazione prima della pubblicazione. Corretti bundle npm e dipendenze vulnerabili, da ultimo Axios/Moment; nessuna esclusione CVE aggiunta.
- Separati DDNS pubblico WireGuard e API privata `.21`, corretti routing/TLS e allineato kubectl alla versione K3s `v1.34.6+k3s1`.
- Preparato MQTT TLS sulla VM con CA privata, account/ACL distinti e persistenza conservata; creati tre Secret MQTT e ConfigMap CA. Il proprietario ha eseguito la migrazione verificata tramite SHA256.
- Creati automaticamente i due Secret osservabilità mancanti con token InfluxDB limitati al bucket e autenticazione Node-RED bcrypt. Conservati Secret originali e file Node-RED precedenti.
- Eseguiti preflight, dry-run server, apply e rollout di InfluxDB, Node-RED, Grafana, consumer audit, simulatore e consumer IA.

## Evidenze

| Controllo | Esito verificato |
|---|---|
| Test/training | 165 test Python; controlli Node-RED e gate IA superati |
| Build/scansioni | Sei build, security scan e integrazione superati; immagini pubblicate |
| API | Risposta privata con TLS verificato: `v1.34.6+k3s1` |
| Credenziali | `grafana-influxdb` e `nodered-auth` creati, nessun valore nei log |
| Storage | PVC dati InfluxDB, Grafana e Node-RED invariati; nuovo PVC configurazione InfluxDB |
| Workload | Tutti e sei i rollout completati |
| Smoke cluster | Salute Node-RED/InfluxDB, Grafana e datasource, cinque query coerenti con il repository, temperatura/umidità recenti persistite |

Le immagini distribuite usano i sei tag della release sopra indicata. Un successivo commit di sola documentazione non genera nuove immagini né cambia il codice in esecuzione.

## Revisione dopo il deploy

Ricontrollati renderer, riferimenti a Secret, indirizzo broker, porta TLS e query del collaudo. La pipeline ha validato manifest e riferimenti prima dell'apply; le query live corrispondono alla release. Nessuna ulteriore incoerenza funzionale è emersa da questi controlli. Corrette nel README le affermazioni obsolete su deploy non avvenuto, Secret ancora mancanti e inferenza ancora sulla vecchia base; lo storico rimane nel registro attività.

Il laboratorio non è qualificato come impianto industriale. Questo run non prova backup/ripristino, durabilità a guasti del nodo o enforcement delle NetworkPolicy tramite client negati. Le policy sono state applicate; i test di guasto e permessi eseguiti in Docker non vengono presentati come prove sul cluster. OpenPLC resta opzionale e fuori dai sei rollout. Il listener legacy MQTT 1883 è stato preservato; la sua dismissione richiede verifica dei client precedenti.

Al push della documentazione GitHub segnala ancora [un avviso Dependabot MODERATE, numero 2](https://github.com/davidevaloroso-sys/ot-security/security/dependabot/2). Il dettaglio non è accessibile con il connettore disponibile né dalla sessione browser non autenticata; pacchetto e applicabilità non sono stati verificati e l'avviso non viene dichiarato risolto. Questo conteggio è distinto dall'audit npm e dal gate HIGH/CRITICAL superati nella CI della release.

## Accesso e documentazione

Node-RED usa `ot-admin`; la password iniziale è conservata in `nodered-auth`, chiave `NODE_RED_ADMIN_PASSWORD`, per recupero locale da parte dell'amministratore Kubernetes. Grafana conserva le credenziali originali di `observability-secrets`. Non copiare valori in report o chat.

[Registro attività](REMEDIATION-STATUS.md) · [Rete/TLS](K3S-TLS.md) · [Secret e recupero da errori](K3S-SECRETS.md) · [Checklist estesa](K3S-COLLAUDO.md) · [Report cloud nel progetto OT-Security](https://chatgpt.com/c/6abc6b51-6920-83eb-b695-db0133a2b4cc).
