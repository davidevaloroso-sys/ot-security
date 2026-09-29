# Correzioni OT-Security — 28 settembre 2026

Base analizzata: `0cb9d376d490579d7110350305967920433a7251`.
Queste modifiche non costituiscono una release collaudata e non sono state distribuite sulla VM. La pubblicazione del codice su GitHub richiede comunque i gate CI prima del rilascio delle immagini.

## Aggiornamento del job del 29 settembre 2026

Il commit `60ac14165ce8180119e851780d5a0f33cfb1a026` è presente su `main`. La [CI associata](https://github.com/davidevaloroso-sys/ot-security/actions/runs/36480856992) ha completato con successo test, build e integrazione completa, ma ha ancora fallito il job `security_scan`; di conseguenza pubblicazione e deploy sono stati correttamente saltati.

Le verifiche locali hanno confermato 65 test Python, 28 test Node-RED, runtime Node-RED reale, training e preflight. Il comando di runtime richiede esplicitamente `NODE_RED_RUNTIME`; con il runtime installato passa. `kubectl` è installato ma non ha `current-context` e tenta `localhost:8080`; Docker Desktop non espone il daemon. Non è stato possibile eseguire un dry-run server, un rollout o un controllo post-deploy.

## Correzioni implementate

- Il consumer IA conserva solo i campi validati del contratto. Un'estensione JSON con un numero fuori intervallo non arresta più il worker; i campi aggiuntivi non gonfiano gli allarmi oltre 16 KiB. `event_id` usa il payload normalizzato.
- Python e Node-RED applicano lo stesso limite di 128 punti di codice Unicode agli alert.
- Node-RED scarta e contabilizza singoli punti definitivamente rifiutati dal DB (413/422 o 400 con errore esplicito di parsing), senza bloccare tutti i messaggi successivi. Continua a ritentare errori generici 400, di autorizzazione, configurazione, rete e disponibilità. Non registra il corpo della risposta o il payload.
- Il collaudo risolve la porta InfluxDB corrente dopo i riavvii, verifica veri record CSV e richiede il PUBACK delle pubblicazioni. Un errore di autorizzazione della query non viene più confuso con un timeout di persistenza.
- Il training applica soglie di regressione del laboratorio pari a 0.95 per precisione e recall della classe anomala quando le variabili sono vuote o mancanti. Gli override espliciti sono registrati. Questi valori non attestano idoneità per impianti reali.

## Verifiche eseguite

| Verifica locale | Esito |
|---|---|
| Python, ambiente isolato 3.12.14 | 65 test superati |
| Node.js 24.19.0, componenti di acquisizione | 28 test superati |
| Runtime Node-RED reale, broker e server HTTP di test | Flusso, login amministrativo e persistenza superati |
| Training sul dataset incluso | 10.000 righe, split 8.000/2.000; precisione e recall anomalia 1.0, gate superati |
| Caricamento modello e inferenza di avvio | Superati |
| Bandit, soglia Medium+ / confidenza Medium+ | Superata; restano 9 segnalazioni Low |
| npm audit delle dipendenze di produzione, nodo e runtime | Zero vulnerabilità riportate |
| Rendering manifest e preflight offline | Superati |

La CI usa Python 3.11: questa matrice deve ancora essere rieseguita in CI. I test di regressione del consumer usano anche modelli controllati per isolare i casi limite; non sostituiscono il modello reale o l'integrazione completa.

## Immagini: miglioramenti proposti e problemi aperti

Scansioni remote eseguite con Trivy 0.74.0 e database aggiornato il 28/09/2026. I rapporti locali sono in `test-results/python-alpine.json` e `test-results/influx-alpine.json` (ignorati da Git). I conteggi sono occorrenze per pacchetto/binario, non necessariamente CVE distinte.

| Componente | Proposta / evidenza | Stato |
|---|---|---|
| Audit e simulatore | Base ufficiale `python:3.11-alpine`, digest `cd04730b8511def3fbf14204d66a0c1536f290b8e896ed5a94cd64cb15ac1356`; nessun HIGH/CRITICAL nei pacchetti OS della base scansionata | Dockerfile aggiornati; build e scansione delle immagini finali da eseguire |
| Strumenti Python nella base Alpine | Due HIGH in `jaraco.context` e `wheel`; i Dockerfile rimuovono pip/setuptools/wheel dopo l'installazione | Verificare l'assenza effettiva nell'immagine finale, non assumere un esito verde dalla sola base |
| InfluxDB | Variante ufficiale 2.9.1 Alpine, digest `38e81dd3af50d085704d970815210dae3d094c5a8a70d7a8f336716889022ea2`; zero HIGH/CRITICAL OS | Manifest aggiornato; compatibilità del container e dei PVC da collaudare |
| Binari InfluxDB Alpine | `dasel`: 21 HIGH; `influx`: 16 HIGH; `influxd`: 33 HIGH | **70 segnalazioni HIGH ancora aperte**; richiedono aggiornamento/ricompilazione upstream dei binari e dipendenze Go |
| Consumer IA | scikit-learn 1.6.1 non dispone di wheel musllinux per Python 3.11 x86_64, verificato con download solo binari | Base Debian conservata; le segnalazioni della CI precedente non sono risolte. Valutare build musl separata o altra base compatibile, con training e collaudo |
| Grafana | L'ultima release ufficiale consultata è ancora 13.2.2, già in uso; la CI originale segnala dipendenze vulnerabili nei binari/plugin | Nessuna correzione verificata; attendere una release corretta o preparare un rebuild upstream riproducibile e collaudato |

Non sono state aggiunte esclusioni CVE, abbassate severità o disabilitati gate. Il workflow continua a impedire la pubblicazione in presenza di scansioni o integrazione fallite. Non migrare a InfluxDB 3 come semplice aggiornamento: il percorso attuale dipende dalle API/Flux di InfluxDB 2.

## Verifiche bloccate e prossimi passi

1. Rendere disponibile Docker Linux o usare un runner autorizzato per riprodurre localmente le quattro build; la CI ha già eseguito build e integrazione con esito positivo.
2. Risolvere le segnalazioni residue nei binari upstream e nell'immagine IA, poi ripetere tutte le scansioni senza esclusioni generiche. La base `python:3.11-slim-bookworm` aggiornata continua a mostrare 55 HIGH e 5 CRITICAL OS senza fix, oltre a due HIGH Python correggibili; il passaggio Alpine non è compatibile con le wheel musllinux di scikit-learn 1.6.1.
3. Per InfluxDB 2.9.1 Alpine la base OS non mostra HIGH/CRITICAL, ma i binari `dasel`, `influx` e `influxd` restano colpiti da vulnerabilità Go upstream. Non sostituire InfluxDB 2 con InfluxDB 3 senza una migrazione progettata: il sistema usa API e Flux di InfluxDB 2.
4. Fornire un kubeconfig verificato per `https://192.168.1.12:6443`, accesso al broker TLS e Secret necessari; eseguire preflight, dry-run server e rollout solo dopo una CI verde.
5. Dopo il deploy, verificare readiness, dashboard, NetworkPolicy, backup/ripristino e incoerenze del codice; quindi aggiornare nuovamente README e questo rapporto con SHA, namespace e risultati effettivi.

Il deploy K3s resta disabilitato. Nessuna connessione al broker o alla VM di laboratorio è stata eseguita.

Riferimenti: [CI della base](https://github.com/davidevaloroso-sys/ot-security/actions/runs/36306512360), [log integrazione precedente](https://github.com/davidevaloroso-sys/ot-security/actions/runs/36306512360/job/109107832832), [log scansioni precedenti](https://github.com/davidevaloroso-sys/ot-security/actions/runs/36306512360/job/109107832707), [Grafana 13.2.2](https://github.com/grafana/grafana/releases/tag/v13.2.2).
