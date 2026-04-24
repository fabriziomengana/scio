import requests
from bs4 import BeautifulSoup
import json
import os
import time
from datetime import datetime
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_extra_details(url, headers):
    try:
        time.sleep(0.3)
        res = requests.get(url, headers=headers, timeout=10, verify=False)
        if res.status_code != 200: return {}
        detail_soup = BeautifulSoup(res.text, 'html.parser')
        modalita = detail_soup.find('div', class_='views-field-field-dettagli').find('div', class_='field-content').get_text(strip=True) if detail_soup.find('div', class_='views-field-field-dettagli') else ""
        ore = detail_soup.find('div', class_='views-field-field-ore').find('div', class_='field-content').get_text(strip=True) if detail_soup.find('div', class_='views-field-field-ore') else ""
        note = detail_soup.find('div', class_='views-field-body').find('div', class_='field-content').get_text(strip=True) if detail_soup.find('div', class_='views-field-body') else ""
        return {"modalita": modalita, "ore": ore, "note": note}
    except: return {}

def scrape_cgsse():
    base_url = "https://cgsse.it/calendario-scioperi"
    nuovi_dati = []
    anno_corrente = datetime.now().year
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}

    for page in range(0, 5): 
        print(f"Scansione pagina {page}...")
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
                if dt_obj.year != anno_corrente: continue
            except: continue

            link_tag = row.find('a', href=True)
            url_det = "https://cgsse.it" + link_tag['href'] if link_tag else ""
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
                'url_fonte': url_det
            }
            nuovi_dati.append(sciopero)
    return nuovi_dati

def salva_dati(dati):
    if not dati: return
    anno = datetime.now().year
    nome_file = f"data_{anno}.json"

    if os.path.exists(nome_file):
        with open(nome_file, 'r', encoding='utf-8') as f:
            try: archivio = json.load(f)
            except: archivio = []
    else: archivio = []

    id_esistenti = {str(item['id_sciopero']): i for i, item in enumerate(archivio)}
    aggiunti = 0
    for s in dati:
        my_id = str(s['id_sciopero'])
        if my_id in id_esistenti:
            archivio[id_esistenti[my_id]] = s
        else:
            archivio.append(s)
            aggiunti += 1

    with open(nome_file, 'w', encoding='utf-8') as f:
        json.dump(archivio, f, ensure_ascii=False, indent=4)
    print(f"Fine. Ho aggiunto {aggiunti} nuovi scioperi nel file {nome_file}.")

if __name__ == "__main__":
    salva_dati(scrape_cgsse())
