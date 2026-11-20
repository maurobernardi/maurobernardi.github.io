# Eseguire source('critical-notes/run.R') dal progetto RStudio.
# Questa istruzione definisce le funzioni, senza avviare analisi o chiamate API.
local({
 files<-as.character(unlist(lapply(sys.frames(),function(x)x$ofile)))
 own<-files[basename(files)=='run.R']
 project<-if(length(own))dirname(dirname(normalizePath(tail(own,1))))else getwd()
 choose_python<-function(){
  candidates<-c(Sys.getenv('CRITICAL_NOTES_PYTHON'),file.path(project,'critical-notes/.venv/bin/python'),
                unname(Sys.which('python3')),
                file.path(Sys.getenv('HOME'),'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'))
  for(py in unique(candidates[nzchar(candidates)&file.exists(candidates)])){
   status<-suppressWarnings(system2(py,c('-c',shQuote('import pypdf')),stdout=FALSE,stderr=FALSE))
   if(identical(status,0L))return(py)
  }
  stop('Serve Python 3 con pypdf: seguire critical-notes/README.md oppure impostare CRITICAL_NOTES_PYTHON.')
 }
 launch<-function(args){
  py<-choose_python()
  result<-system2(py,c(shQuote(file.path(project,'critical-notes/critic.py')),args))
  if(result!=0)stop('Operazione non completata: consultare il messaggio, senza inviare chiavi API nella chat.')
  invisible(file.path(project,'private-notes/critical-notes/index.html'))
 }
 prepare<-function(pdf=NULL,arxiv=NULL,title=NULL){
  if(is.null(pdf)==is.null(arxiv))stop('Specificare uno solo fra pdf e arxiv.')
  args<-c('--prepare',if(!is.null(pdf))c('--pdf',shQuote(normalizePath(pdf,mustWork=TRUE)))else c('--arxiv',shQuote(arxiv)))
  if(!is.null(title))args<-c(args,'--title',shQuote(title))
  launch(args)
 }
 discuss<-function(arxiv=NULL,pdf=NULL,title=NULL,allow_local_upload=FALSE){
  if(is.null(pdf)==is.null(arxiv))stop('Specificare uno solo fra pdf e arxiv.')
  if(!is.null(pdf)&&!isTRUE(allow_local_upload))stop('Per inviare il testo del PDF locale al fornitore configurato impostare allow_local_upload=TRUE; per la sola estrazione usare prepare_paper().')
  args<-if(!is.null(pdf))c('--pdf',shQuote(normalizePath(pdf,mustWork=TRUE)),'--allow-local-upload')else c('--arxiv',shQuote(arxiv))
  if(!is.null(title))args<-c(args,'--title',shQuote(title))
  launch(args)
 }
 shortlist<-function(limit=2){
  if(length(limit)!=1||is.na(limit)||limit!=as.integer(limit))stop('limit deve essere intero.')
  launch(c('--shortlist','--limit',as.character(limit)))
 }
 assign('prepare_paper',prepare,envir=.GlobalEnv)
 assign('discuss_paper',discuss,envir=.GlobalEnv)
 assign('discuss_shortlist',shortlist,envir=.GlobalEnv)
 message('Funzioni disponibili: prepare_paper(), discuss_paper(), discuss_shortlist(). Nessuna API contattata.')
})
