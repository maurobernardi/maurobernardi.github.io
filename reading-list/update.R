# Dal progetto RStudio, eseguire source('reading-list/update.R').
# Scarica i feed arXiv; il modello linguistico è disattivato per impostazione iniziale.
local({
 files<-as.character(unlist(lapply(sys.frames(),function(x)x$ofile)))
 own<-files[basename(files)=='update.R']
 root<-if(length(own))dirname(dirname(normalizePath(tail(own,1))))else getwd()
 py<-unname(Sys.which('python3'))
 if(!nzchar(py))stop('Python 3 non trovato.')
 result<-system2(py,shQuote(file.path(root,'reading-list/reader.py')))
 if(result!=0)stop('Aggiornamento non completato: la pagina precedente è stata conservata se nessun feed era disponibile.')
 message('Reading list aggiornata: ',file.path(root,'docs/reading-list.html'))
})
