# source('automation/run.R') defines functions; it does not fetch or send anything.
local({
 files<-as.character(unlist(lapply(sys.frames(),function(x)x$ofile)))
 own<-files[basename(files)=='run.R']
 project<-if(length(own))dirname(dirname(normalizePath(tail(own,1))))else getwd()
 launch<-function(tasks,network=TRUE,analyze_notes=FALSE){
  candidates<-c(Sys.getenv('RESEARCH_BOTS_PYTHON'),Sys.getenv('CRITICAL_NOTES_PYTHON'),file.path(project,'critical-notes/.venv/bin/python'),unname(Sys.which('python3')),file.path(Sys.getenv('HOME'),'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'))
  candidates<-unique(candidates[nzchar(candidates)&file.exists(candidates)])
  if(!length(candidates))stop('Python 3 non trovato.')
  py<-candidates[1]
  if('notes'%in%tasks){
   ready<-vapply(candidates,function(x)identical(suppressWarnings(system2(x,c('-c',shQuote('import pypdf')),stdout=FALSE,stderr=FALSE)),0L),logical(1))
   if(any(ready))py<-candidates[which(ready)[1]]
  }
  args<-c(shQuote(file.path(project,'automation/maintenance.py')),'--tasks',shQuote(paste(tasks,collapse=',')))
  if(isTRUE(network))args<-c(args,'--network')
  if(isTRUE(analyze_notes))args<-c(args,'--analyze-notes')
  code<-system2(py,args)
  if(code!=0)warning('Alcuni controlli non sono stati completati: consultare il report.')
  target<-file.path(project,'private-notes/automation/reports/index.html')
  message('Report locale: ',target)
  invisible(target)
 }
 assign('research_update',function(network=TRUE,analyze_notes=FALSE)launch(c('publications','links','packages','digest','notes'),network,analyze_notes),.GlobalEnv)
 assign('check_website',function(network=TRUE)launch('links',network),.GlobalEnv)
 assign('check_publications',function(network=TRUE)launch('publications',network),.GlobalEnv)
 assign('monitor_packages',function(network=TRUE)launch('packages',network),.GlobalEnv)
 assign('weekly_digest',function()launch('digest',FALSE),.GlobalEnv)
 assign('prepare_reading_notes',function(network=TRUE,analyze=FALSE)launch('notes',network,analyze),.GlobalEnv)
 assign('configure_nvidia',function(model){
  if(missing(model)||!nzchar(model))stop('Specificare un identificativo di modello abilitato nel proprio account NVIDIA NIM.')
  key<-Sys.getenv('NVIDIA_API_KEY')
  if(!nzchar(key)){
   if(!requireNamespace('rstudioapi',quietly=TRUE))stop('Impostare NVIDIA_API_KEY nell’ambiente locale o usare RStudio con rstudioapi; non inserire chiavi nella chat.')
   key<-rstudioapi::askForPassword('NVIDIA API key — solo sessione R locale')
   if(is.null(key)||!nzchar(key))stop('Configurazione annullata.')
  }
  Sys.setenv(NVIDIA_API_KEY=key,CRITICAL_NOTES_MODEL=model,CRITICAL_NOTES_BASE_URL='https://integrate.api.nvidia.com/v1')
  rm(key)
  message('NVIDIA NIM configurato per questa sessione R. Nessuna chiamata API effettuata e nessuna chiave scritta su file.')
  invisible(TRUE)
 },.GlobalEnv)
 message('Disponibili: research_update(), check_website(), check_publications(), monitor_packages(), weekly_digest(), prepare_reading_notes(). Nessuna operazione avviata.')
})
