import csv,json,sys
from datetime import datetime,timezone,timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'investor_trends.json'
JS_OUT=ROOT/'data'/'investor_trends.js'
FIELDS=['individual','foreign','institution','financial','insurance','trust','other_financial','bank','pension','private_fund','state','other_corp']

def number(value):
    value=(value or '').replace(',','').replace('+','').replace('%','').strip()
    return float(value) if value else None

def main():
    if len(sys.argv)!=2: raise SystemExit('usage: python scripts/import_investor_trends.py <csv>')
    source=Path(sys.argv[1])
    with source.open(encoding='cp949',newline='') as handle: rows=list(csv.reader(handle))[1:]
    records=[]
    for row in rows:
        item={'date':row[0].replace('/','-'),'index':number(row[1]),'trade_value':number(row[5])}
        item.update({name:number(row[i+6]) for i,name in enumerate(FIELDS)})
        records.append(item)
    records.sort(key=lambda x:x['date'])
    dates=[x['date'] for x in records]
    if len(dates)!=len(set(dates)): raise ValueError('duplicate trading dates')
    seoul=timezone(timedelta(hours=9))
    data={'schema_version':1,'status':'user_provided','unit':'억원','updated_at':datetime.now(seoul).isoformat(timespec='seconds'),'source':source.name,'records':records}
    compact=json.dumps(data,ensure_ascii=False,separators=(',',':'))
    OUT.write_text(compact+'\n',encoding='utf-8')
    JS_OUT.write_text('window.INVESTOR_TRENDS='+compact+';\n',encoding='utf-8')
    print(json.dumps({'rows':len(records),'first':dates[0],'last':dates[-1]},ensure_ascii=False))

if __name__=='__main__': main()
