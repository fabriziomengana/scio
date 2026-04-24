import requests
from bs4 import BeautifulSoup
import json
import os
import time
from datetime import datetime
import urllib3

# Disabilita avvisi SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_extra_details(url, headers):
    try:
        time.sleep(0.3)
        res = requests.get(url, headers=headers, timeout=10, verify=False)
        if res.status_code != 200: return {}
        detail_soup = BeautifulSoup(res.text, 'html.parser')
        
        mod_div = detail_soup.find('div', class_='views-field-field-dettagli')
        modalita = mod_div.find('div', class_='field-content').get_text(strip=True) if mod_div else ""
        
        ore_div = detail_soup.find('div', class_='views-field-field-ore')
        ore = ore_div.find('div', class_='field-content').get_text(strip=True) if ore_div else ""
        
        note_div = detail_soup.find('div', class_='views-field-body')
        note = note_div.find('div', class_='field-content').get_text(strip=True) if note_div else ""

        allegati = []
        intervento_section = detail_soup.find('section', id='intervento-section')
        if intervento_section:
            links = intervento_section.find_all('a', href=True)
            for link in links:
                if '.pdf' in link['href'].lower():
                    pdf_url = "https://cgsse.it" + link['href'] if link['href'].startswith('/') else link['href']
                    allegati.append(pdf_url)

        return {"modalita": modalita, "ore": ore, "note": note, "pdf": allegati}
    except:
        return {}

def scrape_cgsse():
    base_url = "https://cgsse.it/calendario-scioperi"
    nuovi_dati = []
    anno_corrente = datetime.now().year
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}

    # Scansioniamo le prime 5 pagine per coprire bene i nuovi inserimenti e le modifiche
    for page in range(0, 5):
        print(f"Scansione pagina {page}...")
        try:
            res = requests.get(base_url, params={'page': page}, headers=headers, timeout=20, verify=False)
            soup = BeautifulSoup(res.text, 'html.parser')
            rows = soup.find_all('li', class_='table-row views-row')
            if not rows: break

            for row in rows:
                data_div = row.find('div', class_='views-field-field-data-inizio')
                if not data_div: continue
                data_str = data_div.get_text(strip=True).replace('Data', '').strip()
                
                try:
                    dt_obj = datetime.strptime(data_str, "%d-%m-%Y")
                    # Filtriamo solo l'anno corrente
                    if dt_obj.year != anno_corrente: continue
                except: continue

                link_tag = row.find('a', href=True)
                url_det = "https://cgsse.it" + link_tag['href'] if link_tag else ""
                
                print(f"  -> {data_str} - {url_det.split('/')[-1]}")
                extra = get_extra_details(url_det, headers) if url_det else {}

                sciopero = {
                    'id_sciopero': url_det.split('/')[-1] if url_det else data_str,
                    'data': data_str,
                    'anno': anno_corrente,
                    'settore': row.find('div', class_='views-field-nothing-2').get_text(strip=True).replace('Settore', '').strip(),
                    'azienda': row.find('div', class_='views-field-nothing').get_text(strip=True).replace('Azienda', '').strip(),
                    'sindacato': row.find('div', class_='views-field-nothing-5').get_text(strip=True).replace('Sindacato', '').strip(),
                    'ambito': "Nazionale" if row.find('img', alt='sciopero nazionale') else row.find('div', class_='views-field-nothing-1').get_text(strip=True).replace('Ambito geografico', '').strip(),
                    'stato': "Revocato" if row.find('img', alt='sciopero revocato') else "Confermato",
                    'modalita': extra.get('modalita', ''),
                    'ore': extra.get('ore', ''),
                    'note': extra.get('note', ''),
                    'documenti_pdf': extra.get('pdf', []),
                    'url_fonte': url_det
                }
                nuovi_dati.append(sciopero)
        except Exception as e:
            print(f"Errore: {e}")
    return nuovi_dati

def salva_dati(dati):
    if not dati: return
    anno_corrente = datetime.now().year
    nome_file = f"data_{anno_corrente}.json" # Salvataggio nella root come richiesto

    if os.path.exists(nome_file):
        with open(nome_file, 'r', encoding='utf-8') as f:
            try:
                archivio = json.load(f)
            except: archivio = []
    else:
        archivio = []

    # Aggiornamento intelligente: se ID esiste sovrascrive (gestisce revoche), altrimenti aggiunge
    id_esistenti = {str(item['id_sciopero']): i for i, item in enumerate(archivio)}
    
    for s in dati:
        my_id = str(s['id_sciopero'])
        if my_id in id_esistenti:
            archivio[id_esistenti[my_id]] = s
        else:
            archivio.append(s)

    with open(nome_file, 'w', encoding='utf-8') as f:
        json.dump(archivio, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    estratti = scrape_cgsse()
    salva_dati(estratti)
    print("Fine processo.")
