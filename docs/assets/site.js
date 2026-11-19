(function(){
 var root=document.documentElement,theme=document.querySelector('.theme-toggle'),menu=document.querySelector('.menu-toggle'),links=document.getElementById('navigation');
 if(!theme||!menu||!links)return;
 root.classList.add('js');
 var groups=Array.from(document.querySelectorAll('.nav-group'));
 function setTheme(value){root.dataset.theme=value;theme.setAttribute('aria-pressed',String(value==='dark'));theme.textContent=value==='dark'?'Light mode':'Dark mode';}
 var stored;try{stored=localStorage.getItem('academic-theme')}catch(e){}
 var localPreview=window.location&&window.location.protocol==='file:';
 var previewTheme=localPreview?new URLSearchParams(window.location.search).get('theme'):null;
 setTheme(previewTheme==='dark'||(previewTheme!=='light'&&stored==='dark')?'dark':'light');
 // Local HTML files may have separate browser storage; carry the choice between pages.
 if(localPreview)document.addEventListener('click',function(e){
  var a=e.target.closest&&e.target.closest('a[href]');if(!a)return;
  var destination=new URL(a.href,window.location.href);
  if(destination.protocol==='file:'&&/\.html$/.test(destination.pathname)){destination.searchParams.set('theme',root.dataset.theme);a.href=destination.href;}
 });
 theme.addEventListener('click',function(){var t=root.dataset.theme==='dark'?'light':'dark';setTheme(t);try{localStorage.setItem('academic-theme',t)}catch(e){}});
 menu.addEventListener('click',function(){var opened=links.classList.toggle('open');menu.setAttribute('aria-expanded',String(opened));});
 groups.forEach(function(group){group.addEventListener('toggle',function(){if(group.open)groups.forEach(function(other){if(other!==group)other.open=false;});});});
 document.addEventListener('click',function(e){groups.forEach(function(group){if(!group.contains(e.target))group.open=false;});});
 document.addEventListener('keydown',function(e){if(e.key==='Escape'){groups.forEach(function(group){if(group.open){group.open=false;group.querySelector('summary').focus();}});if(links.classList.contains('open')){links.classList.remove('open');menu.setAttribute('aria-expanded','false');menu.focus();}}});
})();
