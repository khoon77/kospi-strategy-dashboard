import json,os,time,urllib.parse,urllib.request
from datetime import date,datetime,timedelta,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; FILE=ROOT/'data'/'market.json'; JS_FILE=ROOT/'data'/'market.js'; SEOUL=timezone(timedelta(hours=9)); ENDPOINT=os.getenv('KRX_INDEX_ENDPOINT') or 'https://data-dbg.krx.co.kr/svc/apis/idx/kospi_dd_trd'
def number(v):
 if v in (None,'','-'):return None
 return float(str(v).replace(',',''))
def fetch(day,key):
 req=urllib.request.Request(ENDPOINT+'?'+urllib.parse.urlencode({'basDd':day.strftime('%Y%m%d')}),headers={'AUTH_KEY':key,'User-Agent':'kospi-strategy-dashboard/1.0'})
 with urllib.request.urlopen(req,timeout=30) as res: payload=json.load(res)
 rows=payload.get('OutBlock_1') or []
 row=next((x for x in rows if str(x.get('IDX_NM','')).strip().upper() in ('KOSPI','코스피')),None)
 if not row:return None
 return {'date':day.isoformat(),'open':number(row.get('OPNPRC_IDX')),'high':number(row.get('HGPRC_IDX')),'low':number(row.get('LWPRC_IDX')),'close':number(row.get('CLSPRC_IDX')),'change_pct':number(row.get('FLUC_RT')),'volume':number(row.get('ACC_TRDVOL')),'trade_value':number(row.get('ACC_TRDVAL')),'foreign_spot_net':None,'foreign_futures_net':None,'source':'KRX Open API'}
def save(data,records):
 data.update(status='live',message='KRX 2016년 이후 지수 데이터',updated_at=datetime.now(SEOUL).isoformat(timespec='seconds'),records=sorted(records.values(),key=lambda x:x['date']));compact=json.dumps(data,ensure_ascii=False,separators=(',',':'));FILE.write_text(compact+'\n',encoding='utf-8');JS_FILE.write_text('window.MARKET_DATA='+compact+';\n',encoding='utf-8')
def main():
 key=os.getenv('KRX_AUTH_KEY','').strip()
 if not key:raise SystemExit('KRX_AUTH_KEY is required')
 data=json.loads(FILE.read_text(encoding='utf-8')); records={r['date']:r for r in data.get('records',[])}; day=date.fromisoformat(os.getenv('BACKFILL_START') or '2016-01-04'); end=date.fromisoformat(os.getenv('BACKFILL_END') or datetime.now(SEOUL).date().isoformat()); done=0
 while day<=end:
  if day.weekday()<5 and day.isoformat() not in records:
   try:
    row=fetch(day,key)
    if row:records[row['date']]=row
   except Exception as exc:
    print(f'{day}: {exc}; checkpointing and stopping');save(data,records);raise
   done+=1
   if done%50==0:save(data,records);print(f'checkpoint: {done} requests, {len(records)} trading days')
   time.sleep(.12)
  day+=timedelta(days=1)
 save(data,records);print(f'backfill complete: {len(records)} trading days')
if __name__=='__main__':main()
