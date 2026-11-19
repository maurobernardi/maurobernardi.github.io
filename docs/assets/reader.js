(function(){
 var key='mauro-reading-list-saved',saved=new Set(),cards=Array.from(document.querySelectorAll('.paper')),status=document.getElementById('save-status');
 try{var raw=JSON.parse(localStorage.getItem(key)||'[]');if(Array.isArray(raw))saved=new Set(raw.filter(function(x){return typeof x==='string'}));}catch(e){}
 status.textContent='Saved flags are stored only in this browser; they do not control which papers enter the persistent thematic library.';
 var search=document.getElementById('paper-search'),only=document.getElementById('saved-only');
 function refresh(){var text=search.value.toLowerCase();cards.forEach(function(card){var id=card.dataset.paperId,b=card.querySelector('.save-paper'),on=saved.has(id);b.textContent=on?'Saved to read':'Save to read';b.setAttribute('aria-pressed',String(on));card.hidden=(only.checked&&!on)||card.textContent.toLowerCase().indexOf(text)<0;});}
 cards.forEach(function(card){card.querySelector('.save-paper').addEventListener('click',function(){var id=card.dataset.paperId;if(saved.has(id))saved.delete(id);else saved.add(id);try{localStorage.setItem(key,JSON.stringify(Array.from(saved)));status.textContent='Saved in this browser only. Saved flags do not sync across devices; relevant papers are retained separately in the thematic library.';}catch(e){status.textContent='Browser storage is unavailable; saved flags will last only for this page session.';}refresh();});});
 search.addEventListener('input',refresh);only.addEventListener('change',refresh);refresh();
})();
