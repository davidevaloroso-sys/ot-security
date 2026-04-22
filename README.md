# OT Security Lab on Ubuntu Server + K3s

## 1. Descrizione generale
Questo repository documenta un laboratorio tecnico costruito su **Ubuntu Server** e **K3s**, progettato come piattaforma reale per attività di cybersecurity, DevSecOps, automazione infrastrutturale, simulazione OT/IoT e futura integrazione con componenti di monitoring e SIEM. L'ambiente non nasce come test isolato, ma come base operativa modulare su cui validare configurazioni di rete, orchestrazione di servizi containerizzati, flussi dati MQTT e controlli di sicurezza applicabili a use case di laboratorio e proof-of-concept.

L'architettura attuale prevede un cluster K3s composto da **1 master** e **1 worker**, con possibilità di espansione futura. Il nodo master è già configurato con indirizzo IP statico **192.168.1.21/24** sull'interfaccia **ens33** tramite **Netplan**. Nel laboratorio è già presente anche un **Raspberry Pi simulato / sensor node**, implementato per generare valori random e inviarli a un **broker MQTT**, così da simulare un endpoint OT/IoT all'interno del flusso dati del progetto.

## 2. Obiettivi del laboratorio
Gli obiettivi principali del laboratorio sono i seguenti:

- Costruire una base Kubernetes leggera e riproducibile usando K3s.
- Disporre di un'infrastruttura minima ma reale per testare workflow DevSecOps.
- Simulare componenti OT/IoT attraverso un sensor node software-based.
- Preparare il progetto a pipeline CI/CD, automazione e controlli di sicurezza.
- Predisporre il contesto tecnico per logging centralizzato, monitoring e futura integrazione SIEM.
- Mantenere una struttura repository ordinata, estendibile e orientata a sperimentazione professionale.

## 3. Architettura completa
L'architettura del laboratorio è composta da più livelli logici che cooperano tra loro:

1. **Infrastructure layer**: Ubuntu Server come base del nodo master e cluster K3s come piano di orchestrazione.
2. **Cluster layer**: 1 nodo master e 1 nodo worker, con estensione prevista in futuro.
3. **Application / simulation layer**: componenti containerizzati, script operativi e simulatore Raspberry Pi / sensor node.
4. **Messaging layer**: broker MQTT come punto di raccolta dei dati provenienti dal sensore simulato.
5. **Security / observability layer**: area progettuale destinata a CI/CD, security checks, monitoring e futura integrazione SIEM.

### Vista logica
```text
+-----------------------------------------------------------+
|                    OT Security Lab                        |
+-----------------------------------------------------------+
| Ubuntu Server                                             |
| └── K3s Cluster                                           |
|     ├── Master node (static IP 192.168.1.21/24 - ens33)   |
|     └── Worker node                                       |
|                                                           |
| Simulated Raspberry Pi / Sensor Node                      |
| └── Random data generator                                 |
|     └── MQTT publish ---> Broker MQTT                     |
|                                                           |
| Repository assets                                         |
| ├── k3s/                                                  |
| ├── scripts/                                              |
| ├── Dockerfile                                            |
| ├── main.py / main-2.py                                   |
| ├── requirements.txt                                      |
| └── cicd-k3s.yml                                          |
|                                                           |
| Planned layers                                            |
| ├── CI/CD hardening                                       |
| ├── Security controls                                     |
| ├── Monitoring                                            |
| └── Future SIEM integration                               |
+-----------------------------------------------------------+
```

## 4. Topologia del cluster K3s
Il cluster è attualmente definito con una topologia semplice ma funzionale, pensata per essere stabile, chiara e facilmente espandibile:

- **1 master node**: nodo di controllo del cluster.
- **1 worker node**: nodo destinato all'esecuzione di workload e test operativi.
- **Espansione futura**: possibilità di aggiungere ulteriori worker o componenti specializzati.

Questa topologia consente di mantenere bassa la complessità iniziale, pur offrendo già una separazione concreta tra controllo del cluster e capacità computazionale distribuita. È una scelta coerente con un laboratorio orientato a sperimentazione DevSecOps, simulazione di servizi e validazione progressiva di automazioni.

## 5. Dettaglio master e worker
### Master node
Il master rappresenta il nodo centrale del cluster K3s ed è il punto di riferimento per amministrazione, orchestrazione e verifica operativa. Su questo nodo è già stata completata la configurazione di rete con IP statico tramite Netplan.

**Dettagli confermati del master:**
- Sistema base: Ubuntu Server.
- Ruolo: K3s master.
- Interfaccia: `ens33`.
- IP statico: `192.168.1.21/24`.
- Configurazione rete: Netplan.

### Worker node
È previsto ed è parte della topologia attuale del laboratorio come secondo nodo del cluster. Non sono stati forniti in questa fase dettagli tecnici aggiuntivi sul sistema operativo, IP, naming o configurazione del worker, quindi tali informazioni non vengono inventate e restano da documentare in modo puntuale nel repository quando disponibili.

## 6. Configurazione di rete del master
La rete del master è stata configurata in modalità statica per garantire stabilità del nodo di controllo e continuità operativa dei servizi cluster. In un laboratorio DevSecOps o OT-oriented, mantenere un endpoint stabile per il control plane è fondamentale per automazioni, collegamento dei nodi, troubleshooting, inventory e futura integrazione con sistemi di raccolta log o monitoraggio.

### Parametri confermati
- Interfaccia di rete: `ens33`
- Indirizzo IP: `192.168.1.21/24`
- Tipo di configurazione: statica
- Metodo di gestione: Netplan

### Verifica IP e interfaccia
```bash
ip addr show ens33
ip -4 addr show ens33
hostname -I
ip route
```

### Verifica connettività di base
```bash
ping -c 4 127.0.0.1
ping -c 4 192.168.1.21
ip neigh
```

## 7. Configurazione Netplan e IP statico
La gestione della rete è stata eseguita con Netplan, che su Ubuntu Server costituisce il metodo standard per definire configurazioni persistenti di interfaccia e routing. Il dato certo da evidenziare è che il master K3s utilizza l'IP statico **192.168.1.21/24** su **ens33**.

### Verifica configurazione Netplan
```bash
sudo netplan get
ls -l /etc/netplan/
sudo netplan generate
sudo netplan try
sudo netplan apply
```

### Esempio coerente di configurazione
> Nota: questo esempio mostra la struttura minima coerente con i dati confermati; eventuali gateway, DNS o altre direttive devono essere riportati solo se realmente presenti nell'ambiente.

```yaml
network:
  version: 2
  ethernets:
    ens33:
      dhcp4: false
      addresses:
        - 192.168.1.21/24
```

### Controlli post-applicazione
```bash
networkctl status ens33
ip addr show ens33
ip route
```

## 8. Raspberry Pi simulato / sensor node
Uno dei componenti già integrati nel laboratorio è un **Raspberry Pi simulato**, usato come **sensor node** software. Questo elemento è importante perché introduce nell'architettura una sorgente dati dinamica, utile per simulare dispositivi OT/IoT e validare il flusso di telemetria verso un broker MQTT.

Il sensore simulato genera **valori random** e li pubblica tramite MQTT. In termini architetturali, questo componente rappresenta un endpoint field-like che consente di testare:

- emissione periodica di dati;
- struttura di un producer MQTT;
- comportamento di un device simulato in laboratorio;
- flussi applicativi utili a logging, monitoring e security analytics futuri.

Questa parte del progetto è già significativa perché introduce un pattern realistico: generazione dati → pubblicazione sul broker → possibile raccolta, elaborazione o correlazione successiva.

## 9. Flusso dati verso il broker MQTT
Il flusso dati del Raspberry Pi simulato può essere descritto in modo semplice e funzionale:

1. Il processo applicativo genera valori random.
2. I valori vengono serializzati secondo la logica implementata nello script Python.
3. Il client MQTT stabilisce la connessione al broker.
4. I dati vengono pubblicati su uno o più topic MQTT.
5. Il broker riceve i messaggi e li rende disponibili a consumer, strumenti di osservabilità o futuri collector di sicurezza.

### Flusso logico
```text
[Simulated Raspberry Pi / Sensor Node]
          |
          | genera valori random
          v
   [Python application]
          |
          | publish MQTT
          v
      [MQTT Broker]
          |
          +--> futuri consumer / logging / monitoring / SIEM
```

### Esempio realistico di logica applicativa
Il repository include file applicativi come `main.py` o `main-2.py`; in assenza del contenuto effettivo, il comportamento certo da documentare è che il sensore simulato genera valori casuali e li invia al broker MQTT. Un esempio coerente di esecuzione può essere:

```bash
python3 main.py
```

Un esempio minimale di logica attesa lato Python, coerente con il comportamento dichiarato, può essere il seguente:

```python
import json
import random
import time
from paho.mqtt import client as mqtt_client

broker = "<MQTT_BROKER_HOST>"
port = 1883
topic = "lab/sensors/raspi"
client_id = f"raspi-sim-{random.randint(1000,9999)}"

client = mqtt_client.Client(client_id=client_id)
client.connect(broker, port)
client.loop_start()

while True:
    payload = {
        "device": "raspi-sim",
        "value": random.randint(1, 100),
        "unit": "generic"
    }
    client.publish(topic, json.dumps(payload))
    time.sleep(5)
```

> Se il codice reale usa topic, payload o timing differenti, il README deve essere aggiornato in base all'implementazione effettiva del repository.

## 10. Struttura del repository
In base alle informazioni confermate, il repository include già componenti strutturali e applicativi rilevanti. Una vista sintetica può essere rappresentata così:

```text
.
├── k3s/
├── scripts/
├── Dockerfile
├── main.py / main-2.py
├── requirements.txt
├── cicd-k3s.yml
└── README.md
```

### Ruolo delle directory e dei file principali
- `k3s/`: directory dedicata ai file legati al cluster, ai manifest o alla configurazione Kubernetes/K3s.
- `scripts/`: script operativi, di automazione, bootstrap, verifica o supporto al laboratorio.
- `Dockerfile`: definizione dell'immagine container per componenti applicativi o simulativi del progetto.
- `main.py` / `main-2.py`: entrypoint applicativo del sensore simulato o di componenti Python correlati.
- `requirements.txt`: dipendenze Python necessarie all'esecuzione dell'applicazione.
- `cicd-k3s.yml`: file di pipeline CI/CD orientato all'automazione del progetto.
- `README.md`: documentazione tecnica principale del repository.

## 11. Componenti già presenti
Sulla base del contesto disponibile, i componenti già presenti o già integrati nel progetto sono:

- Ubuntu Server come sistema base del laboratorio.
- Cluster K3s con **1 master** e **1 worker**.
- Master con IP statico **192.168.1.21/24** su **ens33**.
- Configurazione di rete del master tramite **Netplan**.
- Raspberry Pi simulato / sensor node.
- Generazione di valori random lato sensore simulato.
- Invio dei dati verso un broker MQTT.
- Cartella `k3s/`.
- Cartella `scripts/`.
- `Dockerfile`.
- `main.py` oppure `main-2.py`.
- `requirements.txt`.
- File CI/CD come `cicd-k3s.yml`.

## 12. Flusso di lavoro attuale
Il workflow attuale del laboratorio può essere riassunto nelle seguenti fasi operative:

1. Preparazione dell'infrastruttura base su Ubuntu Server.
2. Configurazione del master K3s con rete statica su `ens33`.
3. Gestione del cluster con topologia master + worker.
4. Presenza di componenti repository per Kubernetes, scripting, containerizzazione e pipeline.
5. Esecuzione del sensore simulato per generazione dati random.
6. Pubblicazione dei dati verso il broker MQTT.
7. Preparazione graduale del progetto a osservabilità, automazione, security controls e SIEM.

Questa sequenza mostra che il laboratorio è già oltre la sola fase infrastrutturale: esiste infatti un primo flusso funzionale applicativo e dati, utile a far evolvere il progetto verso scenari più completi di detection, monitoring e security engineering.

## 13. Automazione e CI/CD
Il repository include già l'intenzione esplicita di evolvere verso una gestione più automatizzata, supportata anche dalla presenza di un file di pipeline come `cicd-k3s.yml`. In questa fase, la pipeline va interpretata come base di lavoro per consolidare processi di build, verifica e deployment controllato.

### Finalità dell'automazione
- Standardizzare i passaggi operativi del laboratorio.
- Ridurre errori manuali nelle attività ripetitive.
- Preparare test, build e deploy in modo coerente.
- Introdurre progressivamente controlli DevSecOps.

### Ambiti di automazione previsti o coerenti col progetto
- Build dell'immagine applicativa tramite `Dockerfile`.
- Installazione dipendenze Python da `requirements.txt`.
- Verifica sintattica o funzionale degli script.
- Validazione dei manifest K3s/Kubernetes.
- Controlli di base sullo stato del cluster.
- Integrazione futura di security scans e quality gates.

### Esempi di controlli operativi
```bash
python3 --version
pip3 install -r requirements.txt
python3 main.py
```

```bash
sudo systemctl status k3s --no-pager
sudo k3s kubectl get nodes -o wide
sudo k3s kubectl get pods -A
```

## 14. Preparazione per SIEM e monitoring
Il progetto è pensato fin dall'inizio per facilitare una futura integrazione con strumenti di monitoring e SIEM. Questo non significa che il SIEM sia già attivo, ma che l'architettura sta già prendendo forma in modo compatibile con una successiva fase di raccolta, normalizzazione e correlazione degli eventi.

### In che modo il progetto si prepara al SIEM
- Presenza di un nodo master stabile con IP statico, utile come riferimento infrastrutturale.
- Presenza di un cluster K3s su cui distribuire componenti di raccolta o telemetry agent.
- Presenza di un flusso dati MQTT da un sensore simulato, utile per testare eventi applicativi o telemetria OT/IoT.
- Presenza di cartelle e componenti repository che favoriscono automazione e standardizzazione.
- Impostazione del laboratorio orientata a logging, monitoring e sicurezza, non solo a esecuzione applicativa.

### Tipologie di dati potenzialmente utili per SIEM
- Log di sistema del nodo Ubuntu Server.
- Log del servizio `k3s`.
- Eventi del cluster Kubernetes.
- Log applicativi del simulatore Raspberry Pi.
- Eventi di connessione e pubblicazione MQTT.
- Futuri log di pipeline, deployment e security checks.

### Comandi utili per preparazione e verifica
```bash
sudo journalctl -u k3s -n 100 --no-pager
sudo journalctl -xe --no-pager
sudo k3s kubectl get events -A --sort-by=.metadata.creationTimestamp
sudo k3s kubectl describe node $(hostname)
```

### Monitoring e SIEM: stato attuale
- **Monitoring dedicato**: planned.
- **Collector / agent centralizzati**: planned.
- **Integrazione SIEM completa**: planned.
- **Correlazione eventi OT/IoT**: planned.

## 15. Note di progetto / Design choices
Alcune scelte architetturali emergono già con chiarezza:

- **K3s invece di Kubernetes full-size**: scelta adatta a un laboratorio leggero, rapido da gestire e comunque realistico.
- **IP statico sul master**: scelta fondamentale per stabilità operativa, troubleshooting e futura integrazione con servizi dipendenti dal control plane.
- **Topologia 1 master + 1 worker**: equilibrio tra semplicità iniziale e separazione reale dei ruoli nel cluster.
- **Raspberry Pi simulato**: permette di introdurre subito un flusso OT/IoT senza dipendere da hardware fisico.
- **MQTT come bus di messaggistica**: scelta coerente con simulazioni sensor-based, telemetria e use case edge/lab.
- **Repository già predisposto per script, Docker e CI/CD**: scelta utile per trasformare il laboratorio in piattaforma ripetibile e professionale.

## 16. Roadmap futura
La roadmap del progetto, sulla base dello stato attuale, può essere delineata così:

- Consolidamento completo della documentazione del cluster.
- Formalizzazione del worker node con dettagli tecnici aggiuntivi.
- Versionamento più strutturato dei manifest K3s e delle automazioni.
- Rafforzamento della pipeline CI/CD.
- Introduzione di controlli di sicurezza automatizzati.
- Aggiunta di componenti di monitoring.
- Integrazione futura con SIEM.
- Ampliamento della simulazione OT/IoT con ulteriori sensori o topic MQTT.
- Eventuale espansione del cluster con nodi aggiuntivi.

## 17. Troubleshooting essenziale
Di seguito alcuni comandi utili per verifiche rapide dell'infrastruttura e del cluster.

### Verifica IP e rete
```bash
ip addr show ens33
ip route
networkctl status ens33
ping -c 4 192.168.1.21
```

### Verifica stato K3s
```bash
sudo systemctl status k3s --no-pager
sudo journalctl -u k3s -n 100 --no-pager
```

### Verifica nodi del cluster
```bash
sudo k3s kubectl get nodes -o wide
sudo k3s kubectl get pods -A
sudo k3s kubectl get svc -A
```

### Controllo base del cluster
```bash
sudo k3s kubectl cluster-info
sudo k3s kubectl get events -A --sort-by=.metadata.creationTimestamp
sudo k3s kubectl describe node $(hostname)
```

### Controllo networking di base
```bash
ss -tulpen
sudo lsof -i -P -n
ip neigh
```

### Kubeconfig per utente locale
```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown "$USER":"$USER" ~/.kube/config
export KUBECONFIG=~/.kube/config
kubectl get nodes
```

## 18. Conclusione
Questo progetto rappresenta una piattaforma di laboratorio concreta, costruita per evolvere progressivamente da infrastruttura K3s minimale a ambiente più completo per DevSecOps, simulazione OT/IoT, automazione, monitoring e futura integrazione SIEM. Lo stato attuale mostra già elementi chiave di maturità tecnica: **cluster K3s con 1 master e 1 worker**, **master con IP statico 192.168.1.21/24 su ens33**, struttura repository orientata all'automazione e presenza di un **Raspberry Pi simulato** che genera valori random e li invia a un **broker MQTT**.

Il repository costituisce quindi una base credibile e professionale per sviluppare use case di cybersecurity applicata, orchestrazione container, raccolta eventi e sperimentazione security-oriented in un contesto di laboratorio reale.
