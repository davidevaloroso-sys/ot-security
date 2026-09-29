# Accesso privato K3s e verifica TLS

La VM `192.168.1.21` ospita K3s, WireGuard e MQTT. Il DDNS identifica solo
l'IP pubblico del router per stabilire il tunnel:

```text
Runner GitHub -> k3s--lab.cloud-ip.cc:51820/UDP -> router -> WireGuard VM .21
             -> tunnel WireGuard -> https://192.168.1.21:6443
Pod K3s      -> broker MQTT TLS 192.168.1.21:8883
```

L'endpoint WireGuard è definito nel workflow, con port forwarding UDP 51820
verso la VM. Il vecchio Secret GitHub `WG_ENDPOINT` non viene più letto.
Il nome pubblico deve risolvere verso l'IP WAN del router; non viene aggiunto
a `/etc/hosts` né usato per verificare il certificato K3s.

La CI copia `K3S_KUBECONFIG` in un file temporaneo privato e ne normalizza solo
il cluster del contesto attivo con `scripts/preflight.py --prepare-kubeconfig`:

- server `https://192.168.1.21:6443`;
- eventuale `tls-server-name` precedente rimosso, per verificare l'IP del server;
- CA, credenziali e altri contesti conservati;
- configurazioni con proxy o verifica TLS disabilitata rifiutate;
- contenuti del file mai stampati, permessi 0600 e cleanup a fine job.

Il Secret GitHub non viene modificato: anche la copia già salvata con endpoint
DDNS o localhost viene adattata. Per l'uso manuale impostare direttamente il
server privato nel proprio kubeconfig ed eliminare l'eventuale override DNS.

## Verifica sulla VM Ubuntu

Questo comando usa CA e credenziali del kubeconfig locale e verifica il
certificato per l'IP della VM senza modificarne la configurazione:

```bash
sudo k3s kubectl --kubeconfig=/etc/rancher/k3s/k3s.yaml \
  --server=https://192.168.1.21:6443 \
  --tls-server-name=192.168.1.21 \
  --request-timeout=15s get --raw=/version
```

Il risultato atteso è un JSON con `gitVersion`. Non occorre aggiungere il DDNS
ai SAN del certificato API. Se il certificato non include nemmeno l'IP privato,
aggiungere `192.168.1.21` alla lista `tls-san` della configurazione K3s effettiva,
conservando le altre impostazioni, e riavviare K3s prima di ripetere il test.
Il riavvio rende brevemente indisponibile l'API. Non disabilitare la verifica TLS.

## Interpretazione dei controlli

- `--cluster-only` controlla solo l'endpoint e le opzioni del kubeconfig.
- `kubectl get --raw=/version` verifica il collegamento reale e TLS.
- Timeout: verificare destinazione `.21`, handshake WireGuard e routing.
- Errore `x509`: verificare IP SAN e CA. Un messaggio che nomina ancora il DDNS
  indica un vecchio workflow o un kubeconfig non normalizzato.
- L'API privata non richiede un port forwarding pubblico TCP 6443.

Dopo una correzione sulla VM si possono rieseguire i job falliti se lo SHA del
run è ancora quello di `main`; le modifiche al workflow richiedono un nuovo push.
Un test locale riuscito non sostituisce preflight online, rollout e smoke remoto.

Riferimenti: [configurazione K3s](https://docs.k3s.io/installation/configuration),
[opzioni server TLS](https://docs.k3s.io/cli/server) e
[opzioni kubectl](https://kubernetes.io/docs/reference/kubectl/kubectl/).
