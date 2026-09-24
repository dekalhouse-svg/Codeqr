const API_BASE_URL = window.QR_API_BASE_URL || 'http://127.0.0.1:5000';
const texte=document.getElementById('texte'), generer=document.getElementById('generer'), qrcode=document.getElementById('qrcode'), telecharger=document.getElementById('telecharger'), message=document.getElementById('message');
const scanner=document.getElementById('scanner'), scannerZone=document.getElementById('scannerZone'), camera=document.getElementById('camera'), galerie=document.getElementById('galerie'), fichierQR=document.getElementById('fichierQR'), resultat=document.getElementById('resultat'), fermer=document.getElementById('fermerScanner');
let scannerQR=null;
function getUserCode(){return localStorage.getItem('qr_dekal_user_code')}
async function registerUser(){try{const r=await fetch(`${API_BASE_URL}/api/users/register`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_code:getUserCode()})});if(r.ok){const d=await r.json();localStorage.setItem('qr_dekal_user_code',d.user_code);return d.user_code}}catch(e){console.warn('API indisponible',e)}return null}
async function heartbeat(){const code=getUserCode();if(!code)return;try{await fetch(`${API_BASE_URL}/api/users/heartbeat`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_code:code})})}catch(e){}}
const userReady=registerUser();setInterval(heartbeat,300000);
generer.onclick=async()=>{const value=texte.value.trim();message.textContent='';if(!value){message.textContent='Écrivez quelque chose.';return}qrcode.innerHTML='';new QRCode(qrcode,{text:value,width:200,height:200});telecharger.classList.remove('hidden');const code=await userReady||getUserCode();if(code){try{await fetch(`${API_BASE_URL}/api/qr/generate`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_code:code,content:value})})}catch(e){}}};
telecharger.onclick=()=>{const image=qrcode.querySelector('img');const canvas=qrcode.querySelector('canvas');const a=document.createElement('a');a.download='qrcode.png';a.href=image?.src||canvas?.toDataURL('image/png');a.click()};
scanner.onclick=()=>{scannerZone.classList.remove('hidden');scanner.classList.add('hidden')};
function afficher(code){resultat.textContent='Résultat : '+code;resultat.classList.remove('hidden')}
camera.onclick=()=>{if(scannerQR)return;scannerQR=new Html5Qrcode('reader');scannerQR.start({facingMode:'environment'},{fps:10,qrbox:{width:250,height:250}},async code=>{afficher(code);await scannerQR.stop();scannerQR.clear();scannerQR=null},()=>{}).catch(()=>{alert("Impossible d'utiliser la caméra. Vérifiez l'autorisation du navigateur.");scannerQR=null})};
galerie.onclick=()=>fichierQR.click();fichierQR.onchange=()=>{const file=fichierQR.files[0];if(!file)return;const reader=new Html5Qrcode('reader');reader.scanFile(file,true).then(code=>{afficher(code);reader.clear()}).catch(()=>{alert('Aucun QR Code détecté dans cette image.');reader.clear()})};
fermer.onclick=async()=>{if(scannerQR){try{await scannerQR.stop();scannerQR.clear()}catch(e){}scannerQR=null}scannerZone.classList.add('hidden');scanner.classList.remove('hidden');resultat.classList.add('hidden')};

function showAd(ad){
  const zone=document.getElementById('adZone');
  if(!zone || !ad || !ad.media_url) return;

  const mediaUrl = ad.media_url.startsWith('http')
    ? ad.media_url
    : `${API_BASE_URL}${ad.media_url}${ad.media_url.includes('?')?'&':'?'}v=${encodeURIComponent(ad.id||Date.now())}`;

  const safeTitle=String(ad.title||'Publicité').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
  zone.classList.remove('hidden');
  zone.innerHTML='';

  const content=document.createElement('div');
  content.className='ad-content';

  const title=document.createElement('div');
  title.className='ad-title';
  title.textContent=ad.title || 'Publicité';
  content.appendChild(title);

  if(ad.media_type==='video'){
    const video=document.createElement('video');
    video.id='dekalAdVideo';
    video.src=mediaUrl;
    video.autoplay=true;
    video.muted=true;
    video.playsInline=true;
    video.loop=true;
    video.controls=true;
    video.preload='auto';
    video.setAttribute('playsinline','');
    video.setAttribute('webkit-playsinline','');

    const sound=document.createElement('button');
    sound.id='adSound';
    sound.type='button';
    sound.className='ad-sound';
    sound.textContent='🔊 Activer le son';

    sound.addEventListener('click',e=>{
      e.preventDefault();
      e.stopPropagation();
      video.muted=!video.muted;
      if(!video.muted) video.volume=1;
      video.play().catch(()=>{});
      sound.textContent=video.muted?'🔊 Activer le son':'🔇 Couper le son';
    });
    document.getElementById('scanner').addEventListener('click', function () {
    document.getElementById('scannerZone').scrollIntoView({
        behavior: 'smooth'
    });
});

    content.appendChild(video);
    content.appendChild(sound);
    video.addEventListener('canplay',()=>video.play().catch(()=>{}));
  }else{
    const img=document.createElement('img');
    img.src=mediaUrl;
    img.alt=safeTitle;
    img.loading='eager';
    img.onerror=()=>{zone.classList.add('hidden');};
    content.appendChild(img);
  }

  if(ad.target_url){
    const link=document.createElement('a');
    link.href=ad.target_url;
    link.target='_blank';
    link.rel='noopener noreferrer';
    link.className='ad-link';
    link.textContent='En savoir plus';
    content.appendChild(link);
  }

  zone.appendChild(content);
}

async function loadAd(){
  const zone=document.getElementById('adZone');
  if(!zone) return;
  try{
    const url=`${API_BASE_URL}/api/public/ads?_=${Date.now()}`;
    const r=await fetch(url,{cache:'no-store',headers:{'Accept':'application/json'}});
    if(!r.ok) throw new Error(`HTTP ${r.status}`);
    const d=await r.json();
    const ads=Array.isArray(d.ads)?d.ads:[];
    console.log('[QR DEKAL] Publicités reçues:', ads);
    if(!ads.length){
      zone.classList.add('hidden');
      zone.innerHTML='';
      return;
    }
    const ad=ads[Math.floor(Math.random()*ads.length)];
    showAd(ad);
  }catch(e){
    console.error('[QR DEKAL] Impossible de charger la publicité:',e);
    zone.classList.add('hidden');
  }
}

loadAd();
setInterval(loadAd, 30000);

// En local, évite qu'une ancienne version du Service Worker bloque l'affichage des publicités.
if('serviceWorker' in navigator){
  navigator.serviceWorker.getRegistrations().then(regs=>regs.forEach(reg=>reg.unregister())).catch(()=>{});
  if(window.caches){
    caches.keys().then(keys=>keys.filter(k=>k.startsWith('qr-dekal-')).forEach(k=>caches.delete(k))).catch(()=>{});
  }
}
