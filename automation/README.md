# Research assistants

This module provides five read-only assistants for the academic website. It never edits publication records, package code or website content automatically. Source failures are reported as unavailable or unverified, rather than interpreted as an absence of publications or a successful check.

## Using RStudio

Open the website project and run:

```r
source('automation/run.R')
research_update()
```

The first command only defines functions. The second checks public sources and writes the local dashboard to `private-notes/automation/reports/index.html`. This folder is excluded from Git and is outside the published `docs` directory.

Individual commands are available:

```r
check_website()                         # local targets and public external links
check_publications()                    # proposals from Crossref, ORCID and arXiv
monitor_packages()                      # configured repositories, guides and CRAN
weekly_digest()                         # no network: uses collected arXiv metadata
prepare_reading_notes()                  # public PDFs, local extraction, no model calls
research_update(network = FALSE)         # offline reports and reading worksheets
```

Python 3.9 or later is required. PDF preparation also requires `pypdf`; the R wrapper looks for a Python installation with that dependency. A failed PDF download or extraction is reported without fabricating a discussion.

## 1. Private reading notes

The notes assistant prepares a worksheet for up to two current shortlist papers, including an attributed abstract and prompts about assumptions, proofs, algorithms, experiments and connections to your research. Existing annotations are never overwritten.

With network access, it invokes the existing `critical-notes` module to download public arXiv PDFs and extract their text. These are **preparatory materials**, not generated critical reviews. Complete model-assisted discussions require a configured API key and model:

```r
prepare_reading_notes(analyze = TRUE)
```

Credentials use `CRITICAL_NOTES_API_KEY` and `CRITICAL_NOTES_MODEL` (or the previously configured NVIDIA/reading-list alternatives). Keys must remain in the environment, never in the repository or chat. The analysis sends extracted public-paper text to the configured provider and may incur provider costs. Without credentials the module prepares the PDF only. The existing critical-notes checks require the entire extracted text to fit the configured chunk budget; it does not silently drop pages. Mathematical extraction can still be imperfect, and generated claims require human verification.

This assistant runs locally only. The public GitHub workflow excludes it and never uploads the private notes or source PDFs. No private manuscript is selected or sent automatically. Its full-text outputs remain under `private-notes/critical-notes/`, while worksheets are under `private-notes/automation/reading-notes/`.

## 2. Publication update proposals

The assistant compares the selected publications CSV with recent Crossref metadata, the configured ORCID record and a public arXiv author search. It normalises DOI identifiers, suppresses obvious duplicates and identifies possible journal versions of listed preprints. A full name match remains a candidate for review, not proof of identity. Initial-only matches are explicitly marked uncertain. ORCID works are used only after the record name matches the configured author name.

The report does not rewrite the bibliography. A selected publications page may deliberately omit a detected paper. Search limits, an incomplete ORCID record and delayed registrations can all reduce coverage. The ORCID identifier comes from the profile supplied by the user and can be changed in `automation/config.json`.

## 3. Website audit

All local HTML links, assets, PDFs and fragments are checked. External HTTP(S) links are checked in a bounded sample with four concurrent workers and explicit timeouts. Authentication restrictions, rate limits and timeouts are kept separate from confirmed HTTP 404/410 failures. Browser-upload sizes above 25 MiB are listed for convenience, even though a Git push has different limits.

The audit checks URLs and availability, not whether a thesis has been correctly attributed or whether the scientific content is correct. It does not bypass restricted repositories.

## 4. R package monitoring

The software CSV supplies the package and repository URLs. The assistant checks guide availability, configured CRAN package versions and check-result tables, up to five recent GitHub Actions runs, the latest release when one exists and up to twenty open issue records. Pull requests are excluded from the issue list. Development packages without a CRAN URL are not reported as missing from CRAN. A repository is never guessed solely from the package name.

This is monitoring of existing results, not a new `R CMD check`, code review or validation of numerical routines. Every report is timestamped so successive reports can be compared.

## 5. Weekly digest

The digest groups relevant papers first collected during the preceding seven days by research topic, with a unique-paper total. A paper can appear in several groups. Each entry links to arXiv and gives a short, explicitly labelled excerpt from the authors’ abstract. It does not pretend to have read the paper or generate unsupported scientific conclusions. The digest preserves dated weekly snapshots locally; its maximum number of entries is configurable.

The persistent thematic library remains a separate feature of the daily reading-list workflow. The weekly digest does not change its ranking, retention or stored records.

## Weekly GitHub reports

The `Research maintenance` workflow runs on Mondays at 08:35 UTC, or manually from Actions. Schedules may be delayed. It runs publication checks, the website audit, software monitoring and the digest. It has read-only repository permissions and creates **downloadable reports**, not commits or deployments.

After a run, open **Actions → Research maintenance → the completed run → Artifacts** and download `research-maintenance-<run number>`. Extract it and open `index.html`. Artifacts are retained for 30 days and contain public-source metadata only. In a public repository, treat those artifacts as accessible to other GitHub users. Private reading notes are deliberately absent.

For local scheduling, an example shell command can be used by an existing personal scheduler:

```sh
python3 /absolute/path/to/maurobernardi-personal-site/automation/maintenance.py --network
```

No local background job, cron entry or API credential is installed automatically. The workflow becomes scheduled only after its files have been pushed to the repository's default branch.

## Settings and verification

`config.json` controls author identity, search bounds, request limits, digest size and the number of reading notes. Topic matching remains in `reading-list/preferences.json`.

```sh
python3 -m unittest discover -s automation/tests -v
```

Tests use synthetic data and simulated HTTP responses. An offline smoke run checks the complete local report pipeline; live checks require network access and are explicitly marked when unavailable.

## NVIDIA NIM: configurazione locale

Il fornitore scelto è NVIDIA NIM, attraverso l’endpoint chat HTTPS documentato in <https://docs.api.nvidia.com/nim/reference/llm-apis>. Scegliere dal proprio account un modello disponibile e abilitato: il catalogo può cambiare, quindi non viene imposto un modello potenzialmente ritirato.

In RStudio:

```r
source('automation/run.R')
configure_nvidia(model = 'IDENTIFICATIVO_DEL_MODELLO_ABILITATO')
prepare_reading_notes(analyze = TRUE)
```

`configure_nvidia()` usa una finestra password di RStudio per la chiave, se non è già presente nell’ambiente. Non scrive la chiave nel progetto e non effettua chiamate al modello. La configurazione vale per la sessione R corrente. Il comando successivo genera le discussioni dei paper pubblici selezionati e può consumare credito del fornitore. Le discussioni già completate per lo stesso articolo e modello vengono riutilizzate; cambiare modello consente di rigenerarle. Per aggiornare contenuti o configurazioni scientifiche della nota, rimuovere esplicitamente il relativo record in `private-notes/automation/reading-notes/jobs.json`.

Le discussioni hanno otto sezioni, riferimenti alle pagine PDF e separano affermazioni dell’articolo, interpretazioni critiche ed estensioni proposte. La corrispondenza delle citazioni al testo estratto viene controllata; la correttezza matematica richiede comunque la lettura umana.
