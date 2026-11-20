# Critical reading notes — secondo bot, privato

Il lettore arXiv seleziona i paper da titoli e abstract. Questo secondo modulo elabora invece il **testo estratto dall'intero PDF**, conserva i riferimenti alle pagine e produce una bozza di discussione critica personalizzata. La lingua iniziale è l'italiano, modificabile in `preferences.json`.

Le note sono scritte in `private-notes/critical-notes/`, fuori da `docs/` e ignorate da Git. Non vengono pubblicate con il sito né inviate a persone. Non sono presentate come un giudizio approvato di Mauro.

## Come usarlo da RStudio

Aprire il progetto e definire le funzioni:

```r
source('critical-notes/run.R')
```

Questo non esegue chiamate API. Il primo passo consigliato è verificare l'estrazione di un PDF:

```r
prepare_paper(pdf='/percorso/articolo.pdf')
```

Il risultato è una cartella privata con PDF, testo pagina per pagina e rapporto di preparazione. Non viene inviata alcuna parte del PDF a un modello.

Dopo aver configurato chiave e modello, per un articolo pubblico su arXiv:

```r
discuss_paper(arxiv='2412.05905', title='Fast QR updating methods for statistical applications')
```

Per un PDF locale, l'opzione esplicita autorizza l'invio del testo estratto al fornitore configurato:

```r
discuss_paper(pdf='/percorso/articolo.pdf', allow_local_upload=TRUE)
```

Per avviare automaticamente la discussione dei primi due articoli della lista corrente:

```r
discuss_shortlist(limit=2)
```

Questa funzione richiede che il primo bot abbia già raccolto articoli live. Se la shortlist è ancora vuota non inventa documenti. La funzione avvia il lavoro quando viene chiamata: al momento non è stata installata una pianificazione periodica del secondo bot.

Aprire poi `private-notes/critical-notes/index.html`: per ogni articolo sono disponibili la nota HTML, il Markdown modificabile, il record JSON e il PDF sorgente.

## Credenziali e fornitore

Il modulo usa un endpoint chat HTTPS OpenAI-compatible, inizialmente NVIDIA NIM, lo stesso tipo di servizio previsto per il primo bot. Configurare le variabili d'ambiente:

- `CRITICAL_NOTES_API_KEY` (oppure `NVIDIA_API_KEY`);
- `CRITICAL_NOTES_MODEL` (oppure `READING_LLM_MODEL`);
- facoltativamente `CRITICAL_NOTES_BASE_URL`, inizialmente `https://integrate.api.nvidia.com/v1`.

Le chiavi non vanno salvate nel codice, nei file del sito o nella chat. Il fornitore riceve il testo estratto e il profilo di ricerca: per manoscritti non pubblici valutare se il servizio scelto è appropriato prima di autorizzare l'invio. Non è stata effettuata alcuna chiamata con credenziali reali durante la preparazione.

Senza chiave o modello il bot si ferma dopo aver conservato la preparazione locale, invece di produrre una falsa discussione. Entrambi i bot usano un profilo personalizzato sui tuoi temi di ricerca: selezione, penalizzazioni adattive e di gruppo, DoF, regressione quantilica e funzionale, inferenza variazionale e calcolo matriciale.

## Le otto parti della nota

1. Problema e contributo.
2. Modello, notazione e assunzioni.
3. Risultati teorici e struttura delle prove.
4. Algoritmi e calcolo.
5. Esperimenti e riproducibilità.
6. Punti di forza e limiti.
7. Collegamenti alla tua ricerca.
8. Domande ed estensioni possibili.

Ogni paragrafo è etichettato come affermazione degli autori, interpretazione critica o proposta. Una proposta non diventa un risultato del paper. Per ciò che manca, il bot deve segnalare che non è stato valutato.

## Elaborazione e limiti

- L'estrazione conserva la posizione di ogni pagina nel PDF. I riferimenti sono quindi alla **pagina del file PDF**, che può differire dal numero stampato.
- Tutto il testo estratto viene suddiviso in blocchi, senza omettere silenziosamente le pagine lunghe. Se il documento supera il limite configurato, l'analisi si ferma.
- Ogni blocco produce osservazioni con brevi estratti letterali; il programma controlla che gli estratti esistano sulle pagine citate.
- La sintesi usa soltanto osservazioni così ancorate e rifiuta riferimenti a osservazioni inesistenti.
- L'estrazione non equivale alla lettura visiva: formule, tabelle, figure e PDF scansionati possono non essere interpretati correttamente. Le pagine con pochissimo testo sono segnalate; OCR non è incluso.
- Questi controlli verificano la **tracciabilità**, non dimostrano che l'interpretazione, una critica matematica o una proposta di ricerca siano corrette. La revisione umana resta necessaria.
- Il bot non esegue il codice degli autori, non certifica le dimostrazioni e non verifica automaticamente tutta la letteratura citata.
- La copia HTML non carica script esterni. Le formule eventualmente prodotte dal modello restano anche nel Markdown, da rivedere ed eventualmente impaginare; la copia HTML essenziale non sostituisce un documento matematico compilato.

Per impostazione iniziale ogni esecuzione tratta al massimo due paper, ogni paper fino a 16 blocchi da 14.000 caratteri. Sono possibili fino a 17 richieste per paper (16 blocchi più sintesi), non solo due richieste in totale. Il limite ai token di risposta non garantisce un costo massimo. Le risposte valide vengono conservate nella cache privata; la chiave include PDF, testo estratto, configurazione, modello, endpoint e versione del prompt.

## Dipendenze

Serve Python 3.10 o successivo e `pypdf`. Il codice cerca prima il Python configurato o un ambiente locale; può utilizzare anche il runtime già disponibile di Codex su questo computer.

Per un ambiente autonomo, dal terminale nella cartella del progetto:

```text
python3 -m venv critical-notes/.venv
critical-notes/.venv/bin/python -m pip install -r critical-notes/requirements.txt
```

In alternativa impostare in R `Sys.setenv(CRITICAL_NOTES_PYTHON='/percorso/python')`.

## Verifiche

```text
python3 -m unittest discover -s critical-notes/tests -v
```

I test con risposte sintetiche sono controlli software; non sono un esempio reale di valutazione scientifica. Per verificare l'estrazione PDF sul proprio ambiente usare `prepare_paper()` prima della prima chiamata al modello.
