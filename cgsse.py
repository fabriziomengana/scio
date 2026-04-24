import requests
from bs4 import BeautifulSoup
import json
import os
import time
from datetime import datetime
import urllib3

# Disabilita avvisi SSL per evitare blocchi su GitHub
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_extra_details(url, headers):
    try:
        time.sleep(0.5)
        res = requests.get(url, headers=headers, timeout=15, verify=False)
        if res.status_code != 200: return {}
        detail_soup = BeautifulSoup(res.text, 'html.parser')
        
        # Estrazione sicura dei dettagli
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
    except Exception as e:
        print(f"  ⚠️ Errore dettagli link {url}: {e}")
        return {}

def scrape_cgsse():
    base_url = "https://cgsse.it/calendario-scioperi"
    nuovi_dati = []
    anno_corrente = datetime.now().year
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    print(f"🚀 Inizio scraping per l'anno {anno_corrente}...")

    for page in range(0, 3): # Iniziamo con 3 pagine per evitare timeout
        print(f"🔎 Scansione pagina {page}...")
        try:
            res = requests.get(base_url, params={'page': page}, headers=headers, timeout=25, verify=False)
            if res.status_code != 200:
                print(f"❌ Errore connessione pagina {page}: {res.status_code}")
                continue
                
            soup = BeautifulSoup(res.text, 'html.parser')
            rows = soup.find_all('li', class_='table-row views-row')
            
            if not rows:
                print("ℹ️ Nessuna riga trovata in questa pagina.")
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
                
                print(f"✅ Trovato sciopero: {data_str}")
                extra = get_extra_details(url_det, headers) if url_det else {}

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
            print(f"❌ Errore critico durante lo scraping: {e}")
            
    return nuovi_dati

def salva_dati(dati):
    anno = datetime.now().year
    nome_file = f"data_{anno}.json"
    
    if not dati:
        print("⚠️ Nessun dato utile estratto, salto il salvataggio.")
        return

    # Caricamento file esistente
    archivio = []
    if os.path.exists(nome_file):
        try:
            with open(nome_file, 'r', encoding='utf-8') as f:
                archivio = json.load(f)
        except Exception as e:
            print(f"⚠️ Errore lettura file esistente: {e}. Ne creerò uno nuovo.")

    # Aggiornamento logico
    id_esistenti = {str(item['id_sciopero']): i for i, item in enumerate(archivio)}
    nuovi_inseriti = 0
    
    for s in dati:
        my_id = str(s['id_sciopero'])
        if my_id in id_esistenti:
            archivio[id_esistenti[my_id]] = s
        else:
            archivio.append(s)
            nuovi_inseriti += 1

    try:
        with open(nome_file, 'w', encoding='utf-8') as f:
            json.dump(archivio, f, ensure_ascii=False, indent=4)
        print(f"💾 File {nome_file} salvato con successo! Nuovi record: {nuovi_inseriti}")
    except Exception as e:
        print(f"❌ Errore durante la scrittura del file: {e}")
        exit(1) # Forza l'errore se non riesce a scrivere

if __name__ == "__main__":
    risultati = scrape_cgsse()
    salva_dati(risultati)
