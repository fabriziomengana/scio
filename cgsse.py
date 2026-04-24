import requests
from bs4 import BeautifulSoup
import json
import os
import time
from datetime import datetime
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_extra_details(url, headers, session):
    try:
        time.sleep(1.5) # Pausa più lunga tra i dettagli
        res = session.get(url, headers=headers, timeout=30, verify=False)
        if res.status_code != 200: return {}
        detail_soup = BeautifulSoup(res.text, 'html.parser')
        
        def get_text_safe(selector_class):
            div = detail_soup.find('div', class_=selector_class)
            if div:
                content = div.find('div', class_='field-content')
                return content.get_text(strip=True) if content else ""
            return ""

        return {
            "modalita": get_text_safe('views-field-field-dettagli'),
            "ore": get_text_safe('views-field-field-ore'),
            "note": get_text_safe('views-field-body')
        }
    except:
        return {}

def scrape_cgsse():
    base_url = "https://cgsse.it/calendario-scioperi"
    nuovi_dati = []
    anno_corrente = datetime.now().year
    
    # Sessione con gestione dei tentativi (Retry)
    session = requests.Session()
    retry = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    
    # Headers molto più completi per sembrare un browser vero
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://cgsse.it/',
        'Connection': 'keep-alive'
    }

    print(f"🚀 Avvio connessione a cgsse.it per l'anno {anno_corrente}...")

    for page in range(0, 3):
        print(f"🔎 Analisi pagina {page}...")
        try:
            # Aggiungiamo un piccolo ritardo prima di ogni pagina
            if page > 0: time.sleep(2)
            
            res = session.get(base_url, params={'page': page}, headers=headers, timeout=35, verify=False)
            
            if res.status_code != 200:
                print(f"❌ Il sito ha risposto con errore {res.status_code}")
                continue
                
            soup = BeautifulSoup(res.text, 'html.parser')
            rows = soup.find_all('li', class_='table-row views-row')
            
            if not rows:
                print("ℹ️ Fine delle righe disponibili.")
                break

            for row in rows:
                data_div = row.find('div', class_='views-field-field-data-inizio')
                if not data_div: continue
                
                data_str = data_div.get_text(strip=True).replace('Data', '').strip()
                
                try:
                    dt_obj = datetime.strptime(data_str, "%d-%m-%Y")
                    if dt_obj.year != anno_corrente: continue
                except: continue

                link_tag = row.find('a', href=True)
                url_det = "https://cgsse.it" + link_tag['href'] if link_tag and link_tag['href'].startswith('/') else link_tag['href'] if link_tag else ""
                
                print(f"✅ Recupero: {data_str}")
                extra = get_extra_details(url_det, headers, session) if url_det else {}

                sciopero = {
                    'id_sciopero': url_det.split('/')[-1] if url_det else data_str,
                    'data': data_str,
                    'anno': anno_corrente,
                    'settore': row.find('div', class_='views-field-nothing-2').get_text(strip=True).replace('Settore', '').strip() if row.find('div', class_='views-field-nothing-2') else "",
                    'azienda': row.find('div', class_='views-field-nothing').get_text(strip=True).replace('Azienda', '').strip() if row.find('div', class_='views-field-nothing') else "",
                    'sindacato': row.find('div', class_='views-field-nothing-5').get_text(strip=True).replace('Sindacato', '').strip() if row.find('div', class_='views-field-nothing-5') else "",
                    'ambito': "Nazionale" if row.find('img', alt='sciopero nazionale') else "Territoriale",
                    'stato': "Revocato" if row.find('img', alt='sciopero revocato') else "Confermato",
                    'modalita': extra.get('modalita', ''),
                    'ore': extra.get('ore', ''),
                    'note': extra.get('note', ''),
                    'url_fonte': url_det
                }
                nuovi_dati.append(sciopero)
        except Exception as e:
            print(f"⚠️ Salto pagina {page} per errore: {e}")
            
    return nuovi_dati

def salva_dati(dati):
    anno = datetime.now().year
    nome_file = f"data_{anno}.json"
    
    if not dati:
        print("🛑 Errore: Non sono riuscito a scaricare nessun dato. Il sito potrebbe bloccare GitHub.")
        return

    archivio = []
    if os.path.exists(nome_file):
        try:
            with open(nome_file, 'r', encoding='utf-8') as f:
                archivio = json.load(f)
        except:
            archivio = []

    id_esistenti = {str(item['id_sciopero']): i for i, item in enumerate(archivio)}
    nuovi = 0
    
    for s in dati:
        my_id = str(s['id_sciopero'])
        if my_id in id_esistenti:
            archivio[id_esistenti[my_id]] = s
        else:
            archivio.append(s)
            nuovi += 1

    with open(nome_file, 'w', encoding='utf-8') as f:
        json.dump(archivio, f, ensure_ascii=False, indent=4)
    print(f"🎉 Successo! File aggiornato con {nuovi} nuovi inserimenti.")

if __name__ == "__main__":
    salva_dati(scrape_cgsse())
