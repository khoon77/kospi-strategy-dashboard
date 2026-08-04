import json,os,sys,urllib.parse,urllib.request
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; FILE=ROOT/'data'/'market.json'; JS_FILE=ROOT/'data'/'market.js'; SEOUL=timezone(timedelta(hours=9)); DEFAULT='https://data-dbg.krx.co.kr/svc/apis/idx/kospi_dd_trd'
def n(v):
 if v in (None,'','-'):return None
 return float(str(v).replace(',',''))
def main():
 key=os.getenv('KRX_AUTH_KEY','').strip()
 if not key: print('KRX_AUTH_KEY not configured; pending data preserved.');return 0
 now=datetime.now(SEOUL); date=(os.getenv('MARKET_DATE') or now.strftime('%Y-%m-%d')).strip(); endpoint=os.getenv('KRX_INDEX_ENDPOINT') or DEFAULT
 req=urllib.request.Request(endpoint+'?'+urllib.parse.urlencode({'basDd':date.replace('-','')}),headers={'AUTH_KEY':key,'User-Agent':'kospi-strategy-dashboard/1.0'})
 try:
  with urllib.request.urlopen(req,timeout=30) as res: payload=json.load(res)
  rows=payload.get('OutBlock_1') or payload.get('output') or []
  row=next((x for x in rows if str(x.get('IDX_NM','')).strip().upper() in ('KOSPI','코스피')),None)
  if not row: print(f'No KOSPI row for {date}; holiday or data pending.');return 0
  rec={'date':date,'open':n(row.get('OPNPRC_IDX')),'high':n(row.get('HGPRC_IDX')),'low':n(row.get('LWPRC_IDX')),'close':n(row.get('CLSPRC_IDX')),'change_pct':n(row.get('FLUC_RT')),'volume':n(row.get('ACC_TRDVOL')),'trade_value':n(row.get('ACC_TRDVAL')),'foreign_spot_net':None,'foreign_futures_net':None,'source':'KRX Open API'}
  data=json.loads(FILE.read_text(encoding='utf-8')); records=[x for x in data.get('records',[]) if x.get('date')!=date]+[rec];records.sort(key=lambda x:x['date'])
  data.update(status='live',message='KRX 지수 수집 완료',updated_at=now.isoformat(timespec='seconds'),records=records);compact=json.dumps(data,ensure_ascii=False,separators=(',',':'));FILE.write_text(compact+'\n',encoding='utf-8');JS_FILE.write_text('window.MARKET_DATA='+compact+';\n',encoding='utf-8');print(f"Collected {date}: {rec['close']}");return 0
 except Exception as e: print(f'Collection failed: {e}',file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
