# AWS Free Tier — Guida Completa FinFlow

> Aggiornata a maggio 2026 con il nuovo sistema a crediti (post luglio 2025).

---

## SEZIONE 1 — Come funziona il Free Tier AWS

---

### 1.1 — Le tre categorie del Free Tier

Il Free Tier non è un blocco unico. È composto da **tre categorie diverse** che funzionano in modo completamente differente.

---

#### Categoria A — Always Free (per sempre, senza scadenza)

Queste risorse sono gratis per sempre, indipendentemente dall'età del tuo account e dal piano scelto.

| Servizio | Limite mensile gratuito | Rilevanza per FinFlow |
|---|---|---|
| **Lambda** | 1.000.000 richieste + 400.000 GB-secondi di compute | Tutte le 4 Lambda (API + 3 consumer) |
| **SQS** | 1.000.000 richieste | Le 3 code SQS |
| **SNS** | 1.000.000 pubblicazioni | Il topic SNS |
| **S3** | 5 GB storage, 20.000 GET, 2.000 PUT | Frontend + audit + lambda packages bucket |
| **CloudFront** | 1 TB di dati in uscita al mese | CDN per il frontend React |
| **CloudWatch** | 10 metriche custom, 5 GB log ingestiti, 3 dashboard | Monitoring delle Lambda |
| **API Gateway HTTP** | 1.000.000 chiamate API al mese | API Gateway di FinFlow |
| **SSM Parameter Store** | Standard parameters: illimitati | Segreti e configurazioni |

Per un progetto personale/portfolio come FinFlow non supererai mai questi limiti.

---

#### Categoria B — 12 Months Free (solo per account creati PRIMA del 15 luglio 2025)

> **Nota:** Se hai creato l'account dopo il 15 luglio 2025 sei sul **nuovo sistema a crediti** (vedi 1.2).
> Questa categoria non si applica al tuo account.

Riportata per riferimento:

| Servizio | Limite mensile gratuito |
|---|---|
| EC2 t2.micro | 750 ore/mese per 12 mesi |
| EBS storage | 30 GB per 12 mesi |
| Elastic IP | 1 IP pubblico se associato a istanza running |
| Data Transfer Out | 100 GB/mese verso internet |

---

#### Categoria C — Free Trials (prove a tempo, specifiche per servizio)

Tipicamente da 30 a 90 giorni dall'attivazione del servizio. Non rilevanti per FinFlow.

---

### 1.2 — Il nuovo sistema a crediti (post 15 luglio 2025)

Dal 15 luglio 2025 AWS ha cambiato il Free Tier per i nuovi account. Invece delle 12 mesi di risorse gratis, il nuovo sistema funziona così:

#### Come funzionano i crediti

I crediti AWS sono **voucher prepagati messi da AWS nel tuo account**, non soldi tuoi. Ogni risorsa che usi viene scalata dal saldo crediti prima che AWS addebiti la tua carta di credito. Finché hai crediti, la carta non viene toccata.

#### Quanto si riceve

- **$100 di crediti immediati** alla registrazione
- **Fino a $100 aggiuntivi** usando certi servizi (EC2, RDS, Lambda, Bedrock, AWS Budgets)
- **Massimo $200 totali**

#### Durata del Free Plan

Il Free Plan scade alla **prima** di queste due condizioni:
1. I crediti si esauriscono
2. Sono passati **6 mesi** dalla registrazione

Alla scadenza AWS **sospende l'account** (non lo cancella — i dati restano). Per continuare bisogna fare upgrade al Paid Plan.

#### Il tuo stato attuale (maggio 2026)

```
Crediti rimanenti:   $158.90
Giorni rimanenti:    180 (scadenza 30 ottobre 2026)
Costo mese corrente: $1.10 (scalato dai crediti, non dalla carta)
```

Al ritmo attuale (~$1.10/mese) i crediti durano molto più dei 6 mesi. Il vero limite è la **scadenza temporale del 30 ottobre 2026**.

#### Cosa fare entro ottobre 2026

Hai due opzioni:

| Opzione | Quando sceglierla | Costo dopo la scadenza |
|---|---|---|
| Upgrade a Paid Plan | Se vuoi continuare ad usare l'infrastruttura | ~$0 per servizi Always Free + ~$8-9/mese per EC2 t2.micro |
| `terraform destroy` | Se il progetto è solo per studio/portfolio | $0 |

---

### 1.3 — Come funzionano le "ore" per le risorse

Il concetto di ore si applica alle risorse che girano continuamente.

#### EC2 — ore di calcolo

- Un mese ha circa 730 ore (365 × 24 ÷ 12)
- Nel vecchio sistema: 750 ore/mese = esattamente 1 istanza t2.micro che gira 24/7
- Nel nuovo sistema a crediti: ogni ora di EC2 t2.micro ha un costo ($0.0116/ora in us-east-1) che viene scalato dai crediti
- Le ore si contano dall'avvio allo stop/terminate
- Un'istanza in stato `stopped` non consuma ore EC2, ma continua a consumare EBS (disco) e Elastic IP

#### Lambda — GB-secondi

Lambda non usa "ore" ma un'unità diversa: **GB-secondi** = memoria allocata in GB × durata in secondi.

- Lambda API di FinFlow: 256 MB = 0.25 GB
- Se gira per 1 secondo → 0.25 GB-secondi consumati
- 400.000 GB-secondi gratuiti/mese (Always Free)
- 400.000 ÷ 0.25 = **1.600.000 secondi di esecuzione** gratis al mese
- Per un progetto personale è praticamente impossibile superare questo limite

---

### 1.4 — Metriche, Log e Alert

#### CloudWatch — il sistema centrale di monitoring

CloudWatch raccoglie automaticamente log e metriche da quasi tutti i servizi AWS.

**Log delle Lambda (automatici):**
Ogni `print()` o `logger.info()` nel codice Python finisce in CloudWatch Logs.
Percorso: `CloudWatch → Log groups → /aws/lambda/finflow-production-api`

**Metriche automatiche delle Lambda (gratis):**

| Metrica | Significato |
|---|---|
| `Invocations` | Quante volte è stata chiamata |
| `Duration` | Quanto tempo ha impiegato (ms) |
| `Errors` | Quante volte ha fallito con eccezione |
| `Throttles` | Quante volte è stata bloccata per troppo traffico |
| `ConcurrentExecutions` | Istanze in esecuzione contemporaneamente |

**Metriche automatiche EC2 (gratis):**

| Metrica | Significato |
|---|---|
| `CPUUtilization` | Percentuale di CPU usata |
| `NetworkIn` / `NetworkOut` | Traffico di rete in entrata/uscita |
| `StatusCheckFailed` | 1 se l'istanza non è raggiungibile |

**Cosa costa in CloudWatch:**

| Cosa | Costo | Gratuito fino a |
|---|---|---|
| Metriche custom scritte nel codice | $0.30/metrica/mese | 10 metriche/mese |
| Log ingestiti | $0.50/GB | 5 GB/mese |
| Dashboard custom | $3/dashboard/mese | 3 dashboard (max 50 metriche ciascuna) |

---

#### Alert e Budget — per non avere sorprese in bolletta

**1. Free Tier Usage Alert (da abilitare):**
AWS manda un'email automatica quando si raggiunge l'85% del limite Free Tier di un servizio.
→ `Billing and Cost Management → Billing Preferences → Receive AWS Free Tier usage alerts`

**2. Zero Spend Budget (il più importante):**
Avvisa appena AWS prevede di addebitare anche solo $0.01 sulla carta.
→ `Billing and Cost Management → Budgets → Create budget → Zero spend budget`

**3. CloudWatch Billing Alarm:**
Secondo livello di sicurezza: scatta quando i costi stimati superano una soglia (es. $5).
→ Obbligatoriamente nella region `us-east-1` → `CloudWatch → Alarms → Create → metrica EstimatedCharges`

---

### 1.5 — Le trappole: risorse che sembrano gratis ma non lo sono

| Trappola | Dettaglio | Come evitarla |
|---|---|---|
| **Elastic IP non associata** | Gratis se associata a istanza running. Se l'istanza è stopped o l'IP è sganciato → ~$3.60/mese | Distruggi l'IP se fermi l'istanza definitivamente |
| **NAT Gateway** | ~$32/mese fissi solo per esistere | Non usato in FinFlow (decisione corretta) |
| **VPC Interface Endpoints** | ~$7.30/endpoint/AZ/mese | Rimossi dal Terraform di FinFlow |
| **EBS volumes orfani** | Se si fa `terminate` di un'EC2, il volume può non essere cancellato | Verificare `delete_on_termination = true` nel Terraform |
| **CloudWatch Logs senza retention** | I log si accumulano: dopo 5 GB si paga | Impostare retention di 7-30 giorni sui Log Groups |
| **Data Transfer Out** | $0.09/GB dopo i primi 100 GB/mese gratuiti | Non un problema per uso personale |
| **Snapshot EBS** | Ogni snapshot rimane e costa $0.05/GB/mese | Gestire la lifecycle delle snapshot |

---

### 1.6 — Stato di FinFlow rispetto al Free Tier (maggio 2026)

| Risorsa | Categoria Free Tier | Stato |
|---|---|---|
| EC2 t2.micro (Postgres + Redis + Celery) | Scalato dai crediti | ✅ 1 istanza |
| EBS 30 GB (root volume EC2) | Scalato dai crediti | ✅ dentro i 30 GB |
| Elastic IP | Scalato dai crediti | ✅ sempre associata |
| Lambda × 4 | Always Free | ✅ impossibile superare per uso personale |
| SQS × 3 code | Always Free | ✅ ben dentro i limiti |
| SNS × 1 topic | Always Free | ✅ ben dentro i limiti |
| S3 × 3 bucket | Always Free | ✅ dentro i 5 GB |
| CloudFront | Always Free | ✅ ben sotto 1 TB/mese |
| API Gateway HTTP | Always Free | ✅ ben dentro 1M chiamate/mese |
| SSM Parameter Store | Always Free | ✅ |
| CloudWatch Logs | Always Free | ⚠️ monitorare se le Lambda loggano molto |
| **Costo mensile attuale** | | **$1.10 (scalato dai crediti)** |

---

## SEZIONE 2 — Verifica dei profili AWS

---

### 2.1 — Root vs IAM User

**Root Account:**
- Creato con l'email di registrazione AWS
- Accesso illimitato e irrevocabile a tutto, inclusa la chiusura dell'account
- **Non deve mai essere usato per lavoro quotidiano** — solo per operazioni che solo root può fare (cambio piano di supporto, chiusura account)
- Se le credenziali root vengono compromesse, il danno è totale e irreversibile

**IAM User / IAM Role:**
- Utenti secondari con permessi limitati che crei tu
- Se le credenziali vengono compromesse, il danno è limitato ai soli permessi assegnati
- Terraform e GitHub Actions devono usare un IAM User (o Role), mai il root

---

### 2.2 — Checklist Root Account

**A) MFA abilitata?**
Senza MFA, email + password = accesso totale all'account.
→ Console AWS → nome in alto a destra → `Security credentials → Multi-factor authentication (MFA)`
→ Deve mostrare almeno un dispositivo MFA attivo

**B) Nessuna access key attiva?**
Il root non dovrebbe avere access key (`AWS_ACCESS_KEY_ID`).
→ Stessa pagina → sezione `Access keys` → deve dire "No access keys"

**C) Billing alerts abilitati?**
→ `Billing and Cost Management → Billing Preferences`
→ Abilitare "Receive AWS Free Tier usage alerts"
→ Abilitare "Receive CloudWatch billing alerts"

---

### 2.3 — Checklist IAM User (usato da Terraform e CI/CD)

**D) Permessi minimi necessari (Least Privilege)?**
L'IAM User di Terraform dovrebbe avere solo i permessi per creare/gestire le risorse FinFlow, non `AdministratorAccess` completo.

**E) Le GitHub Actions Secrets usano credenziali IAM (non root)?**
→ GitHub repo → `Settings → Secrets and variables → Actions`
→ Verificare che `AWS_ACCESS_KEY_ID` e `AWS_SECRET_ACCESS_KEY` siano presenti e appartengano a un IAM User

**F) Le access key vengono ruotate periodicamente?**
Raccomandato ogni 90 giorni.

---

### 2.4 — Come verificare i crediti e il Free Tier nella console

**Step 1 — Controlla i crediti:**
`Billing and Cost Management → Credits`
Vedrai: sorgente, importo originale, saldo rimanente, data di scadenza

**Step 2 — Controlla l'uso del Free Tier questo mese:**
`Billing and Cost Management → Free Tier`
Tabella con: servizio, limite gratuito, uso attuale, percentuale

**Step 3 — Controlla i costi per servizio:**
`Billing and Cost Management → Bills → mese corrente`
Breakdown per servizio di quanto stai spendendo (scalato dai crediti)

**Step 4 — Cerca risorse dimenticate:**
`Billing and Cost Management → Cost Explorer → raggruppa per servizio`
Cerca qualsiasi servizio con costo > $0 non previsto

---

### 2.5 — Alert da configurare (se non già fatto)

| Alert | Dove configurarlo | Priorità |
|---|---|---|
| Zero Spend Budget | `Billing → Budgets → Create → Zero spend budget` | Alta |
| Free Tier Usage Alert | `Billing → Billing Preferences` | Alta |
| CloudWatch Billing Alarm a $5 | `CloudWatch (us-east-1) → Alarms → EstimatedCharges` | Media |
