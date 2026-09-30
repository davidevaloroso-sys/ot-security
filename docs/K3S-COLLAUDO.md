# Attività che richiedono il laboratorio acceso

**Esito del 30 settembre:** deploy dei sei workload e smoke applicativo superati nel [run 36744724064](https://github.com/davidevaloroso-sys/ot-security/actions/runs/36744724064). [Report delle verifiche eseguite](DEPLOYMENT-2026-09-30.md). La checklist seguente include anche prove estese non eseguite sul cluster, come ripristino backup, guasti e verifica negativa delle NetworkPolicy.

API K3s e broker MQTT sulla VM: **192.168.1.21**. Il runner apre WireGuard tramite **k3s--lab.cloud-ip.cc:51820/UDP** e interroga **https://192.168.1.21:6443** nel tunnel. Il proprietario ha autorizzato deploy e uso dei Secret GitHub. Il job è abilitato sui push a main dopo tutti i gate; questa checklist non attesta prove già eseguite. Consultare `REMEDIATION-STATUS.md` per gli esiti effettivi.

| Passo | Cosa verificare sul server | Esito atteso |
|---|---|---|
| Accesso | DDNS pubblico WireGuard, route VPN a `.21`, kubeconfig/CA e IP SAN `192.168.1.21` | `python scripts/preflight.py --cluster-only` valida la configurazione; `kubectl --request-timeout=30s get --raw=/version` verifica rete, TLS e risposta API |
| Inventario | Versione K3s, architettura dei nodi, capacità RAM/CPU, storage class, PVC e installazioni precedenti | Nodi Ready; immagini compatibili con l'architettura; spazio sufficiente |
| Backup | Esportazione dei dati InfluxDB, dati Grafana/Node-RED, configurazione broker e conservazione sicura dei Secret | Copie esterne alla VM con una prova di ripristino; nessuna sovrascrittura dei PVC originali |
| Migrazione | Compatibilità dei dati esistenti con InfluxDB 2.9.1, Grafana 13.2.2 e Node-RED 5.0.7 | Migrazione su copia verificata prima del rollout; permessi UID/GID corretti |
| MQTT | Listener 8883, certificato con IP SAN `.21`, CA, account e ACL per i quattro ruoli | TLS verificato; credenziali errate e operazioni fuori ruolo respinte; persistenza broker attiva |
| Secret | Confronto dei nomi/chiavi documentati con quelli presenti, senza esporre valori | `mqtt-credentials` e `observability-secrets` originali conservati; nuove credenziali separate |
| Token InfluxDB | Creazione sul bucket reale dei token write Node-RED e read Grafana | Grafana non scrive, Node-RED non legge o amministra il DB; token conservati nel gestore segreti |
| Registry | Accesso dei nodi alle sei immagini GHCR dello SHA pubblicato | Nessun `ImagePullBackOff`; credenziali registry se il package è privato |
| Preflight | Rendering della release approvata e risoluzione Secret/ConfigMap/PVC | `python scripts/preflight.py rendered` e `kubectl apply --dry-run=server -f rendered` passano |
| Rollout | Applicazione dei manifest e attesa dei sei deployment | Tutti Ready; nessun CrashLoop; Node-RED diventa Ready dopo una scrittura valida |
| Dashboard | Login, datasource, temperatura/umidità, ultima lettura e storico anomalie | Dati recenti e coerenti con i messaggi pubblicati, nessun errore Flux |
| Isolamento | Enforcement delle NetworkPolicy da pod consentiti e non consentiti | InfluxDB raggiungibile solo dai ruoli previsti; UI non pubbliche |
| Guasti | Arresto controllato del broker e del DB, riconnessione, riconsegna QoS1 | Readiness degrada; al ripristino riprende la persistenza; niente conferme premature |
| Durabilità | Riavvio di pod/nodo e ripristino da backup | Dati e configurazioni conservati; ClientId senza sovrapposizioni |
| CD | Environment `lab`, chiavi WireGuard originali, endpoint DDNS dal workflow, copia kubeconfig normalizzata e verifica SHA prima di apply | Il deploy usa la release verificata e raggiunge esclusivamente il laboratorio autorizzato |

## Ordine operativo

1. Accesso, inventario e backup.
2. Broker TLS, credenziali e storage.
3. Bootstrap InfluxDB e token limitati.
4. Release con CI verde, preflight e dry-run server.
5. Rollout, dashboard, isolamento e guasti.
6. Verifica backup/ripristino e registrazione degli esiti.

I comandi di bootstrap e creazione Secret sono nel README. La [verifica delle risorse mancanti](K3S-SECRETS.md) riporta l'inventario iniziale e il successivo completamento della preparazione. Non incollare password, token, chiavi private o kubeconfig in chat. Non eliminare PVC per risolvere problemi di avvio.

## Limiti indipendenti dal server

Il test Docker completo e le scansioni immagini possono essere eseguiti in CI anche con k3s spento. Un runner non disponibile, un blocco del registry o una vulnerabilità upstream senza correzione sono impedimenti separati: accendere la VM non li risolve. Prima del deploy verificare l'esito effettivo della CI e l'esistenza dei sei tag pubblicati. Il preflight rifiuta nodi schedulabili diversi da Linux/amd64; lo smoke `postdeploy_check.py` verifica servizi, query della release e telemetria recente senza provocare guasti sul cluster.

Per dati reali occorre inoltre concordare provenienza, frequenza e schema dei sensori, validare il modello su dati indipendenti e definire soglie/costi dei falsi allarmi. Le letture dello stesso sensore/tipo nello stesso secondo si sovrascrivono nel contratto attuale. OpenPLC richiede un collaudo distinto dell'Editor, del programma PLC e dei protocolli: non è collegato alla pipeline del simulatore.
