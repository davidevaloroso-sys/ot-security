# Preparazione delle credenziali del laboratorio

**Aggiornamento finale del 30 settembre:** i tre Secret MQTT e la CA sono stati creati dalla procedura sulla VM; `grafana-influxdb` e `nodered-auth` sono stati creati dal [run 36744724064](https://github.com/davidevaloroso-sys/ot-security/actions/runs/36744724064), seguito da rollout e smoke riusciti. Il laboratorio è già predisposto: non ripetere la migrazione MQTT o il bootstrap iniziale. L'inventario sottostante documenta il punto di partenza e le procedure restano disponibili per diagnosi e laboratori nuovi.

## Stato verificato il 29 settembre 2026

Il run [36628560125](https://github.com/davidevaloroso-sys/ot-security/actions/runs/36628560125), commit `b70bd07`, ha superato test, sei build, scansioni, integrazione e pubblicazione. L'API privata ha risposto con `v1.34.6+k3s1`; rete e TLS hanno funzionato. Il preflight si è fermato leggendo `grafana-influxdb`, prima del dry-run e dell'apply.

L'inventario eseguito dal proprietario sulla VM ha poi confermato:

| Risorsa in `ot-namespace` | Stato |
|---|---|
| Secret `mqtt-credentials` | Presente, due chiavi; preservare |
| Secret `observability-secrets` | Presente, sette chiavi; preservare |
| Secret `mqtt-raspi-simulator`, `mqtt-ia-consumer`, `mqtt-nodered` | Assenti |
| Secret `nodered-auth`, `grafana-influxdb` | Assenti |
| ConfigMap `mqtt-ca` | Assente |
| Deployment precedenti, incluso OpenPLC | Sette disponibili; questo non attesta la nuova release |

Questi sono Secret **Kubernetes sulla VM**, distinti dai Secret GitHub per la VPN, il kubeconfig e Docker Hub. L'inventario sopra descrive il blocco iniziale. La preparazione MQTT è poi stata completata dal proprietario; la CI può ora creare i soli Secret Node-RED/Grafana mancanti come descritto sotto. Non crea account sul broker e non sovrascrive Secret presenti.

## Preparazione automatica di Node-RED e Grafana

Il run `36740613024` ha confermato come unici prerequisiti mancanti `grafana-influxdb` e `nodered-auth`. `scripts/prepare_observability.py --apply` viene eseguito dalla pipeline dopo la connessione VPN e il controllo dello SHA corrente, prima del preflight e dell'apply dei workload.

La procedura legge `INFLUXDB_ADMIN_TOKEN`, `INFLUXDB_ORG` e `INFLUXDB_BUCKET` da `observability-secrets` senza stamparli. Apre un port-forward solo su localhost, verifica che il database sia già inizializzato e trovi esattamente org/bucket previsti. Emette un token con solo lettura del bucket per Grafana e uno con sola scrittura per Node-RED. Non invoca setup, non modifica dati, PVC, token originali o flussi esistenti.

Per Node-RED esegue nel pod esistente una lettura dei file in `/data` e la generazione bcrypt, senza installare moduli o valutare `settings.js`. Riutilizza la chiave automatica da `.config.runtime.json`; in assenza di credenziali salvate può generarne una nuova. Si ferma prima di emettere token se rileva un `credentialSecret` esplicito o credenziali salvate senza una chiave identificabile. Questi casi richiedono una migrazione specifica, non una sostituzione alla cieca.

Il nuovo utente è `ot-admin`. Il Secret `nodered-auth` conserva anche `NODE_RED_ADMIN_PASSWORD` per il recupero da parte dell'amministratore del cluster; il deployment riceve soltanto l'hash bcrypt, non la password in chiaro. Recuperare la password sul terminale amministrativo, senza incollarla in chat o nei log. I Secret completi già presenti vengono conservati integralmente, senza generare nuove password o token. Secret presenti ma incompleti causano uno stop.

Ogni token appena emesso viene immediatamente inviato al relativo Secret con `create`, mai `apply` o sostituzione. Le autorizzazioni sono identificate dalle descrizioni `ot-security-bootstrap/grafana-influxdb` e `ot-security-bootstrap/nodered-auth`. Un retry riutilizza un'autorizzazione compatibile solo se il server ne rende ancora disponibile il token. **InfluxDB 2.9 non riespone il token dopo la creazione**: se la creazione del Secret fallisce dopo l'emissione, la procedura si ferma e richiede recupero/intervento amministrativo, senza emettere duplicati o revocare nulla. La creazione del token e del Secret non è una transazione atomica.

Senza `--apply` lo script verifica i prerequisiti senza creare Secret o token. Richiede `kubectl`, accesso all'API e permessi di lettura/creazione Secret, exec Node-RED e port-forward InfluxDB. Errori grezzi e valori delle credenziali restano esclusi dai log. Il collaudo `tests/observability_smoke.py` usa InfluxDB e Node-RED reali in container temporanei, con Kubernetes simulato: verifica permessi effettivi, bcrypt, chiave preservata, riesecuzioni e rifiuto di configurazioni ambigue.

Il controllo successivo del proprietario conferma Mosquitto come servizio attivo sull'host, listener `0.0.0.0:1883`, `allow_anonymous false`, password file `/etc/mosquitto/passwd`, configurazione in `/etc/mosquitto/conf.d/ot.conf`. Nessun listener 8883 è emerso; `docker ps` era vuoto. Occorre preparare il broker TLS, oltre ai Secret.

Il preflight aggiornato raccoglie tutti i problemi di lettura e le chiavi assenti o vuote. Distingue `NotFound`, `Forbidden`, `Unauthorized`, errori TLS e timeout, senza stampare dati dei Secret o stderr grezzo. Si ferma comunque prima del deploy. La presenza delle chiavi non dimostra ancora che il broker o il database accettino le credenziali: questo viene verificato nel collaudo applicativo.

## Verifica del broker esistente

Eseguire sulla VM Ubuntu. I comandi leggono porte, stato e percorsi; non stampano il contenuto del password file o della chiave privata:

```bash
sudo ss -lntp | grep -E ':(1883|8883)\b'
systemctl is-active mosquitto
sudo docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'
sudo grep -RnsE '^[[:space:]]*(listener|protocol|cafile|certfile|keyfile|password_file|acl_file|allow_anonymous|require_certificate|use_identity_as_username|include_dir)[[:space:]]' /etc/mosquitto 2>/dev/null
```

Se Mosquitto è in un container, i file possono essere montati altrove: individuare il mount prima di adattare i percorsi. L'assenza di `/etc/mosquitto` sull'host non prova che il broker sia privo di TLS. Non incollare un `docker inspect` completo, che può contenere variabili segrete.

Con il percorso della CA pubblica confermato, verificare il certificato effettivamente servito:

```bash
openssl s_client -connect 192.168.1.21:8883 \
  -CAfile /percorso/confermato/ca.crt \
  -verify_ip 192.168.1.21 -verify_return_error </dev/null
```

Questa prova verifica TLS, non l'autenticazione MQTT. Il certificato deve includere l'IP SAN `.21`. Gli esempi `config/mosquitto.conf.example` e `config/mosquitto.acl.example` sono riferimenti da integrare nella configurazione esistente, senza sostituirla alla cieca. La porta 1883 si chiude dopo la migrazione dei client.

## Migrazione assistita della configurazione rilevata

Dal checkout aggiornato sulla VM Ubuntu, eseguire prima il controllo senza modifiche:

```bash
sudo python3 scripts/prepare_mqtt_tls.py
```

Richiede `k3s`, `openssl`, `mosquitto_passwd`, `systemctl` e accesso amministrativo locale a Kubernetes. Non richiede pacchetti Python aggiuntivi. Verifica le tre direttive di listener/autenticazione rilevate, l'account audit sulla 1883 e l'assenza delle risorse da creare. Accetta anche una singola direttiva globale `persistence true` oppure `persistence false` in `ot.conf`, confermata sulla VM il 30 settembre: ne conserva valore e posizione senza riscrivere il file. Si ferma su valori invalidi o duplicati, altre configurazioni aggiuntive, file di una precedente migrazione o credenziali già predisposte. Il significato della direttiva è documentato nel [manuale Mosquitto](https://mosquitto.org/man/mosquitto-conf-5.html).

Per applicare la preparazione MQTT:

```bash
sudo python3 scripts/prepare_mqtt_tls.py --apply
```

La procedura riavvia brevemente Mosquitto per aggiungere il listener; i client esistenti devono riconnettersi. Mantiene il listener 1883 e il suo password file. Crea una CA privata del laboratorio, un certificato server con IP SAN `192.168.1.21`, tre nuovi account sul listener TLS e ACL separate; conserva l'account audit originale anche sulla 8883. Verifica TLS e i quattro login sulla 8883, più il login audit sulla 1883, senza pubblicare telemetria. Se l'attivazione fallisce, tenta il ripristino della configurazione precedente e il riavvio del servizio.

Soltanto dopo le verifiche crea `mqtt-raspi-simulator`, `mqtt-ia-consumer`, `mqtt-nodered` e `mqtt-ca` con operazioni `create`, mai sostituzione. La CA privata, le credenziali generate e il backup della configurazione rimangono in `/var/lib/ot-security/mqtt-bootstrap` (directory root 0700, file 0600). I file del broker sono in `/etc/mosquitto/ot-security-tls`, con accesso di sola lettura/traversal per il gruppo Mosquitto; la chiave della CA non viene distribuita al broker o al cluster.

**In caso di errore non cancellare i file generati e non rilanciare alla cieca.** Il blocco su file/risorse già presenti impedisce rotazioni involontarie; un errore durante la creazione Kubernetes può lasciare TLS funzionante e solo parte dei nuovi Secret. Conservare lo stato e completare le risorse mancanti con le credenziali già salvate. La procedura non crea ancora `grafana-influxdb` e `nodered-auth`, non migra PVC e non applica i deployment.

Il collaudo riproducibile usa un container temporaneo, senza montare directory della VM:

```bash
docker run --rm -v "$PWD:/work:ro" -w /work python:3.11-alpine \
  sh -c 'apk add --no-cache mosquitto openssl >/dev/null && OT_DISPOSABLE_MQTT_TEST=1 python tests/mqtt_tls_smoke.py'
```

Il test usa un broker reale, un IP loopback con certificato dedicato e risorse Kubernetes simulate. Controlla TLS, login, rifiuto password/IP errati, conservazione del password file precedente, permessi dei file e blocco delle riesecuzioni. Il rollback dopo errore di riavvio è coperto dai test unitari; non è stato provocato un guasto sul broker reale.

## Completamento senza cambiare le credenziali originali

1. Salvare dati e configurazione degli applicativi esistenti prima della migrazione. I deployment attuali usano versioni/configurazioni precedenti.
2. Verificare TLS e creare gli account distinti sul broker, con ACL coerenti con i tre ruoli. Salvare username/password reali in file protetti fuori dal repository. Creare i Secret `mqtt-raspi-simulator`, `mqtt-ia-consumer`, `mqtt-nodered`, ciascuno con `username` e `password`. Conservare l'account audit di `mqtt-credentials`.
3. Creare `mqtt-ca` con la CA del broker effettivamente verificata, chiave `ca.crt`. Non usare la CA K3s al suo posto.
4. Verificare l'InfluxDB esistente tramite port-forward localhost. Usare le credenziali amministrative già conservate per emettere un token write per Node-RED e uno read per Grafana, limitati al bucket reale. Un valore casuale non è un token autorizzato da InfluxDB. Se esistono già file con token validi, riutilizzarli; lo script di provisioning crea nuovi token per entrambi i ruoli e rifiuta di sovrascrivere i file.
5. Completare `nodered-auth` con login, hash bcrypt, chiave di cifratura stabile e token write. Valutare la chiave di cifratura Node-RED esistente prima di cambiarla: una nuova chiave non decifra credenziali salvate con la precedente. Creare `grafana-influxdb` con `INFLUXDB_READ_TOKEN`.
6. Eseguire il preflight e solo dopo il dry-run, rollout e collaudo. La procedura completa e le chiavi sono nel [README](../README.md#bootstrap-e-rilascio-k3s--da-eseguire-nel-collaudo-della-vm).

Per creare il Secret Grafana **solo quando il file protetto contiene un token valido**:

```bash
sudo k3s kubectl -n ot-namespace create secret generic grafana-influxdb \
  --from-env-file=/percorso/protetto/grafana-influxdb.env
```

`create` si ferma se la risorsa è già presente; non cancella o sostituisce credenziali. Il nome della chiave nel file deve essere `INFLUXDB_READ_TOKEN`. Non salvare questo file nel repository e non incollarlo in chat.

In caso di `Forbidden` nel runner, verificare RBAC con **la stessa identità del kubeconfig usato da GitHub**: il fatto che `sudo k3s kubectl` funzioni come amministratore locale non dimostra i permessi del runner. Non sostituire automaticamente il ruolo con `cluster-admin`.

Riferimenti: [creazione di token InfluxDB](https://docs.influxdata.com/influxdb/v2/admin/tokens/create-token/), [lettura risorse con kubectl](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_get/).
