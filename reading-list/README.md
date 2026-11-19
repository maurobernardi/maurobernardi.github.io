# Personal arXiv reading list

Il modulo è parte del progetto del sito, ma separa raccolta e selezione degli articoli dalla grafica delle pagine. Il profilo di selezione definisce temi, parole chiave e autori modificabili in `preferences.json`.

## Argomenti iniziali

- Metodologia e calcolo bayesiani: variational inference, expectation propagation e MCMC.
- Modelli latenti, GLMM e modelli additivi.
- Modelli dinamici, state-space e reti.
- Come interessi collegati: Bayes nonparametrico, sopravvivenza e statistica spaziale.
- Priorità inferiore a deep learning, reinforcement learning e graph neural networks senza un collegamento metodologico statistico sostanziale.
- Categorie: `stat.ME`, `stat.CO`, `stat.AP`.

Il file `preferences.json` contiene argomenti, contesto, parole chiave, elenco degli autori e soglia di selezione. Si può aprire e modificare da RStudio: non serve conoscere Python per regolare il profilo. Al momento non abbiamo aggiunto automaticamente i tuoi ulteriori interessi, per mantenere il punto di partenza richiesto.

## Uso da RStudio

Dalla cartella del progetto:

```r
source('build.R')                 # rigenera il sito dai dati locali, senza rete o API
source('reading-list/update.R')  # recupera i feed e aggiorna la lista
```

Python 3 è necessario, ma non sono richiesti pacchetti Python aggiuntivi. Tutto il modulo usa la libreria standard. È possibile eseguire direttamente `python3 reading-list/reader.py` da un terminale.

## Cosa fa

1. Scarica i tre feed RSS, con tentativi limitati e una pausa fra le categorie.
2. Deduplica gli articoli attraverso l'identificativo arXiv, mantenendo le categorie di cross-listing.
3. Conserva sette giorni dalla prima comparsa nella lista locale, escludendo le revisioni per impostazione iniziale.
4. Assegna un punteggio di pertinenza. In modalità senza API usa regole dichiarate nella pagina. In modalità LLM invia al fornitore configurato solo titoli, abstract, autori e il profilo di interesse.
5. Pubblica al massimo venti articoli sopra la soglia iniziale di 4/10, con un archivio dei candidati e spiegazioni dei punteggi.
6. Ricorda i risultati della valutazione per non ripetere richieste API sullo stesso testo con lo stesso profilo e modello.

Il punteggio non misura qualità scientifica né probabilità di correttezza. Il riassunto LLM, quando attivato, si basa sull'abstract e non implica la lettura del PDF. Le priorità negative hanno un significato semantico nel contesto LLM; le regole offline riconoscono soltanto frasi esplicite e non comprendono da sole il valore metodologico del lavoro.

Gli articoli si possono cercare e segnare come “Saved to read”. Il salvataggio è locale al browser, non si sincronizza tra dispositivi e non conserva il record oltre i sette giorni. Non è un archivio permanente della biblioteca personale.

## Attivare la valutazione LLM

La modalità iniziale è **rules**, quindi non consuma credito API. Per attivare la modalità assistita da un modello linguistico:

- aggiungere nelle impostazioni del repository il secret `NVIDIA_API_KEY`;
- aggiungere la variabile `READING_LLM_MODEL`, con l'identificativo di un modello chat abilitato nel proprio account NVIDIA;
- impostare la variabile `READING_USE_LLM` a `true`.

Il codice usa l'endpoint HTTPS OpenAI-compatible di NVIDIA NIM, configurabile con la variabile d'ambiente `READING_LLM_BASE_URL`. Non è necessario né opportuno scrivere la chiave nel codice o nella chat. Prima di attivare un fornitore, verificare disponibilità del modello, condizioni e costo nel proprio account. Il modulo limita per impostazione iniziale a 40 i candidati valutati dal modello per esecuzione; questo è un limite alle richieste, non una garanzia su spesa o quote.

Senza chiave e modello, o in caso di errori, la pagina segnala la modalità a regole. Le due modalità sono etichettate e i relativi punteggi non vanno trattati come misure perfettamente equivalenti.

## GitHub: passaggi di attivazione dopo la revisione del sito

1. Caricare solo i componenti necessari: `reading-list/`, `docs/` e `.github/workflows/reading-list.yml`, nel repository `maurobernardi.github.io` sul ramo `main`.
2. Per usare questo workflow, in **Settings > Pages > Source** selezionare **GitHub Actions**, invece di “Deploy from a branch”.
3. Per la sola modalità a regole non occorre una chiave. Per LLM configurare i secret e le variabili descritti sopra.
4. Aprire **Actions > Update arXiv reading list > Run workflow** e controllare il primo aggiornamento.
5. Dopo l'attivazione il workflow è programmato nei giorni feriali alle 07:43 UTC (08:43 in Italia in inverno, 09:43 in estate). Il servizio può eseguirlo in ritardo: non è una consegna garantita all'orario esatto.

Il workflow aggiorna solo i dati del lettore e la pagina generata, li salva nel repository e pubblica `docs/`. Le altre pagine devono essere già compilate localmente con `build.R` e caricate quando si modificano i testi. La grafica può cambiare senza cambiare le preferenze.

Se nessun feed è disponibile, l'esecuzione fallisce senza sovrascrivere pagina e dati precedenti. Se fallisce una sola categoria, aggiorna le altre e mostra un avviso. Una normale compilazione locale non attiva alcuna automazione GitHub.

## Verifiche

```text
python3 -m unittest discover -s reading-list/tests -v
```

I test usano fixture RSS esplicitamente sintetiche e mock delle API; queste fixture non vengono mostrate nella pagina pubblica. La pagina iniziale indica chiaramente se non è ancora avvenuto un aggiornamento live.

## Raccolta storica e lista completa dei pertinenti

La shortlist mantiene un massimo di 20 articoli recenti. “All relevant recent papers” mostra tutti i recenti sopra soglia, compresi quelli della shortlist. “All collected recent papers” comprende anche i recenti sotto soglia.

La “Thematic arXiv library” è separata e persistente: `library.py` aggiunge gli articoli dei feed e interroga l’API Atom di arXiv attraverso otto query tematiche. Il primo avvio tenta tutte le query; i successivi ne ruotano una per esecuzione. Ogni richiesta recupera fino a 100 risultati, ordinati per data di invio decrescente, fino a una profondità di 500 risultati per query; il cursore viene poi riportato all’inizio per recuperare novità. Questo limite riguarda la ricerca, non il numero di record già conservati. Le query e le categorie sono modificabili in `preferences.json`, sotto `library`.

La raccolta non è esaustiva di arXiv. I suoi record non scadono dopo sette giorni; la soglia corrente decide quali sono mostrati. La classificazione della biblioteca usa sempre regole, senza chiamate aggiuntive a modelli linguistici. Le chiamate all’API sono intervallate da almeno 3,2 secondi. In caso di indisponibilità si conservano i record precedenti e si mostra un avviso; la raccolta quotidiana può continuare indipendentemente.

Lo stato persistente è in `reading-list/data/library.json`. Non sovrascriverlo, e non sovrascrivere `papers.json`, con copie locali vuote. Il workflow salva entrambi e rigenera la pagina. Le date delle schede indicano la data arXiv di invio quando disponibile, mentre l’intervallo dei feed resta definito dalla prima raccolta locale.
