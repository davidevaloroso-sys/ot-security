# OT Security Lab on Ubuntu Server + K3s

## Abstract
Questo repository documenta un laboratorio cybersecurity basato su **Ubuntu Server** e K3s, progettato come base tecnica per attività DevSecOps, OT Security, automazione operativa e futura integrazione con una piattaforma SIEM. L'ambiente attuale prevede un nodo master già configurato con indirizzamento IP statico sulla rete locale, con l'obiettivo di evolvere verso un laboratorio riproducibile, ordinato e orientato a use case di sicurezza applicativa e infrastrutturale.

Lo scopo del progetto è mantenere una foundation chiara per il provisioning del cluster, la gestione della rete, la validazione dello stato dei servizi e la preparazione di componenti futuri dedicati a logging, osservabilità, detection e integrazione security.

## Architettura
L'architettura attualmente documentata riguarda un nodo master K3s installato su Ubuntu Server, già configurato con IP statico `192.168.1.21/24` sull'interfaccia `ens33` tramite Netplan. Non sono stati forniti dettagli su worker node, componenti OT simulati, servizi applicativi, ingress controller, registry o stack di monitoring; tali elementi devono quindi essere considerati non ancora documentati o futuri.

### Stato attuale
- Sistema operativo: Ubuntu Server.
- Nodo: master K3s.
- Interfaccia di rete: `ens33`.
- Indirizzo IP statico: `192.168.1.21/24`.
- Configurazione rete: Netplan.
- Orientamento progettuale: DevSecOps, OT Security, automazione, futura integrazione SIEM.

### Evoluzione prevista
Le seguenti componenti sono coerenti con l'obiettivo del repository, ma allo stato attuale vanno considerate **future** finché non saranno effettivamente implementate e versionate:
- Aggiunta di worker node al cluster.
- Deployment di workload security-oriented.
- Pipeline di automazione per bootstrap e hardening.
- Raccolta centralizzata log ed eventi.
- Integrazione SIEM e use case OT-specifici.

## Prerequisiti
Prima di procedere con il bootstrap o la manutenzione del laboratorio, è opportuno verificare i seguenti prerequisiti minimi:

- Accesso amministrativo al server Ubuntu.
- Connettività IP locale sulla subnet `192.168.1.0/24`.
- Configurazione corretta di Netplan già applicata.
- Accesso a Internet per installazione pacchetti e bootstrap K3s.
- Utility di base disponibili: `ip`, `ping`, `curl`, `systemctl`, `journalctl`.
- Permessi `sudo` per installazione, verifica servizi e troubleshooting.

Comandi di verifica iniziale:

```bash
hostnamectl
ip addr show ens33
ip route
ping -c 4 192.168.1.1
curl -I https://get.k3s.io
```

## Configurazione rete
Il master è già configurato con indirizzo statico `192.168.1.21/24` su `ens33` tramite Netplan. In assenza del file YAML effettivamente usato nel repository, di seguito viene riportato un esempio tecnico coerente con le informazioni disponibili, da adattare solo se necessario e senza assumere parametri non confermati come gateway o DNS specifici.

### Verifica configurazione corrente
```bash
ip addr show ens33
ip route
sudo netplan get
```

### Esempio di struttura Netplan
> Nota: esempio strutturale; usare solo valori realmente presenti nell'ambiente.

```yaml
network:
  version: 2
  ethernets:
    ens33:
      dhcp4: false
      addresses:
        - 192.168.1.21/24
```

### Applicazione configurazione
```bash
sudo netplan generate
sudo netplan try
sudo netplan apply
```

### Validazione connettività
```bash
ping -c 4 127.0.0.1
ping -c 4 192.168.1.21
ip addr show ens33
ss -tulpen
```

## Installazione K3s
K3s può essere installato sul nodo master tramite script ufficiale. Poiché non sono stati forniti parametri custom di installazione, token, canalizzazioni di versione o configurazioni avanzate, il repository deve documentare un'installazione base del server K3s, dichiarando come future eventuali personalizzazioni.

### Installazione server K3s
```bash
curl -sfL https://get.k3s.io | sh -
```

### Abilitazione e stato servizio
```bash
sudo systemctl enable k3s
sudo systemctl status k3s --no-pager
```

### Accesso a kubectl tramite K3s
```bash
sudo k3s kubectl get nodes
sudo k3s kubectl get pods -A
```

### Kubeconfig locale
Per utilizzare `kubectl` con un utente non root:

```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown "$USER":"$USER" ~/.kube/config
export KUBECONFIG=~/.kube/config
kubectl get nodes
```

### Join di nodi aggiuntivi
La procedura di join di worker node non è ancora documentata nei dettagli forniti e deve quindi essere considerata **futura**.

## Verifica stato cluster
Dopo l'installazione, il cluster deve essere validato a livello di nodo, componenti di sistema e servizi Kubernetes di base.

### Verifiche essenziali
```bash
sudo k3s kubectl get nodes -o wide
sudo k3s kubectl get pods -A
sudo k3s kubectl get svc -A
sudo k3s kubectl cluster-info
sudo k3s kubectl version
```

### Verifica servizio K3s e log
```bash
sudo systemctl status k3s --no-pager
sudo journalctl -u k3s -n 100 --no-pager
```

### Test operativo minimo
```bash
sudo k3s kubectl create namespace lab-test
sudo k3s kubectl get ns
sudo k3s kubectl delete namespace lab-test
```

## Struttura repository
La struttura esatta del repository non è stata fornita in modo navigabile nei dettagli e non deve essere inventata. Di seguito è riportata una struttura professionale **consigliata** e coerente con gli obiettivi del progetto; va considerata futura o da adattare allo stato reale del repo.

```text
.
├── README.md
├── docs/
│   ├── architecture/
│   ├── network/
│   ├── siem/
│   └── troubleshooting/
├── k8s/
│   ├── base/
│   ├── security/
│   └── ot/
├── scripts/
│   ├── bootstrap/
│   ├── checks/
│   └── automation/
├── netplan/
│   └── examples/
└── assets/
```

### Convenzioni consigliate
- `docs/`: documentazione tecnica e operativa.
- `k8s/`: manifest Kubernetes, baseline e futuri deployment.
- `scripts/`: bootstrap, verifiche, automazioni e utility.
- `netplan/`: esempi e versionamento controllato della configurazione di rete.
- `assets/`: diagrammi, output o materiale di supporto non eseguibile.

## Script e automazioni
L'orientamento del progetto include automazione e ripetibilità operativa. Poiché non sono stati descritti script già presenti nel repository, ogni automazione va esplicitamente indicata come esistente solo se effettivamente committata; in questa fase è corretto documentare ciò che è previsto e suggerire pattern minimi di implementazione.

### Aree di automazione previste
- Bootstrap del nodo master.
- Verifica prerequisiti di rete e sistema.
- Health check del cluster K3s.
- Preparazione directory, kubeconfig e permessi.
- Validazione pre-SIEM per log e telemetry.

### Esempio di health check Bash
```bash
#!/usr/bin/env bash
set -euo pipefail

echo "[+] Network interface"
ip addr show ens33

echo "[+] Routing"
ip route

echo "[+] K3s service status"
sudo systemctl is-active k3s

echo "[+] Cluster nodes"
sudo k3s kubectl get nodes -o wide

echo "[+] System pods"
sudo k3s kubectl get pods -A
```

### Esempio di salvataggio log diagnostici
```bash
mkdir -p ./artifacts
sudo journalctl -u k3s --no-pager > ./artifacts/k3s-journal.log
sudo k3s kubectl get nodes -o wide > ./artifacts/nodes.txt
sudo k3s kubectl get pods -A > ./artifacts/pods-all-namespaces.txt
```

## Preparazione SIEM
L'integrazione SIEM è un obiettivo dichiarato ma non ancora implementato nei dettagli disponibili. Di conseguenza, questa sezione deve essere trattata come preparazione tecnica preliminare e non come integrazione già completata.

### Obiettivi preparatori
- Rendere il nodo e il cluster osservabili.
- Centralizzare log di sistema e log dei servizi critici.
- Preparare eventi utili a detection engineering e use case futuri.
- Separare chiaramente baseline infrastrutturale e componenti security.

### Ambiti da predisporre
- Log di sistema del nodo Ubuntu.
- Log del servizio `k3s`.
- Eventi Kubernetes e stato dei namespace.
- Futuri agent/collector per integrazione SIEM.
- Futuri casi d'uso per ambienti OT Security e detection.

### Raccolta preliminare locale
```bash
sudo journalctl -u k3s --since today
sudo journalctl -xe --no-pager
sudo k3s kubectl get events -A --sort-by=.metadata.creationTimestamp
sudo k3s kubectl describe node $(hostname)
```

### Stato implementazione
Le seguenti componenti sono **future** finché non saranno presenti nel repository:
- Integrazione con Wazuh, Elastic, Splunk o altro SIEM.
- Parser, normalizzazione e forwarding dei log.
- Dashboard di detection o correlazione.
- Use case specifici per segmenti OT/ICS.

## Roadmap
La roadmap deve riflettere solo ciò che è coerente con le informazioni disponibili e con l'orientamento dichiarato del progetto.

- Fase 1: consolidamento del nodo master Ubuntu Server + K3s.
- Fase 2: versionamento completo della configurazione di rete e dei controlli di bootstrap.
- Fase 3: introduzione di script di health check e automazione operativa.
- Fase 4: definizione di workload security-oriented e namespace dedicati.
- Fase 5: preparazione della pipeline di osservabilità e raccolta log.
- Fase 6: futura integrazione SIEM.
- Fase 7: estensione verso use case DevSecOps e OT Security più avanzati.

## Troubleshooting
Questa sezione raccoglie verifiche rapide utili in caso di problemi di rete, bootstrap K3s o accesso al cluster.

### Rete non corretta o IP mancante
```bash
ip addr show ens33
sudo netplan get
sudo netplan generate
sudo netplan try
sudo netplan apply
```

### Servizio K3s non attivo
```bash
sudo systemctl status k3s --no-pager
sudo journalctl -u k3s -n 200 --no-pager
sudo systemctl restart k3s
```

### kubectl non configurato per utente locale
```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown "$USER":"$USER" ~/.kube/config
export KUBECONFIG=~/.kube/config
kubectl get nodes
```

### Diagnostica cluster
```bash
sudo k3s kubectl get nodes -o wide
sudo k3s kubectl get pods -A
sudo k3s kubectl get events -A --sort-by=.metadata.creationTimestamp
sudo k3s kubectl describe node $(hostname)
```

### Porte e processi in ascolto
```bash
sudo ss -tulpen
sudo lsof -i -P -n
```

## License
```text
TODO: Add appropriate license for this repository.
```
