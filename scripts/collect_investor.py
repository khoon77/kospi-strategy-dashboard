import json,os,sys,urllib.parse,urllib.request
from datetime import datetime,timezone,timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; FILE=ROOT/'data'/'investor_trends.json'; JS_FILE=ROOT/'data'/'investor_trends.js'; SEOUL=timezone(timedelta(hours=9))
FIELDS={'individual':'INDV_NETBID_TRDVAL','foreign':'FRGN_NETBID_TRDVAL','institution':'ORG_NETBID_TRDVAL','financial':'FIN_INV_NETBID_TRDVAL','insurance':'INSU_NETBID_TRDVAL','trust':'INV_TRST_NETBID_TRDVAL','other_financial':'ETC_FIN_NETBID_TRDVAL','bank':'BANK_NETBID_TRDVAL','pension':'PENS_NETBID_TRDVAL','private_fund':'PEF_NETBID_TRDVAL','state':'NATL_NETBID_TRDVAL','other_corp':'ETC_CORP_NETBID_TRDVAL'}
def n(v):
    if v in (None,'','-'): return None
    return float(str(v).replace(',',''))
def main():
    key=os.getenv('KRX_AUTH_KEY','').strip(); endpoint=os.getenv('KRX_INVESTOR_ENDPOINT','').strip()
    if not key or not endpoint: print('KRX investor endpoint not configured; existing trend data preserved.'); return 0
    day=(os.getenv('MARKET_DATE') or datetime.now(SEOUL).strftime('%Y-%m-%d')).strip()
    req=urllib.request.Request(endpoint+'?'+urllib.parse.urlencode({'basDd':day.replace('-','')}),headers={'AUTH_KEY':key,'User-Agent':'kospi-strategy-dashboard/1.0'})
    try:
        with urllib.request.urlopen(req,timeout=30) as res: payload=json.load(res)
        rows=payload.get('OutBlock_1') or payload.get('output') or []
        row=next((x for x in rows if str(x.get('MKT_NM') or x.get('IDX_NM') or '').strip().upper() in ('KOSPI','유가증권시장')),None)
        if not row: print(f'No KOSPI investor row for {day}.'); return 0
        rec={'date':day,'index':n(row.get('CLSPRC_IDX')),'trade_value':n(row.get('ACC_TRDVAL'))}
        rec.update({name:n(row.get(api_name)) for name,api_name in FIELDS.items()})
        data=json.loads(FILE.read_text(encoding='utf-8')); records={x['date']:x for x in data.get('records',[])}; records[day]=rec
        data.update(status='live',updated_at=datetime.now(SEOUL).isoformat(timespec='seconds'),source='KRX Open API',records=sorted(records.values(),key=lambda x:x['date']))
        compact=json.dumps(data,ensure_ascii=False,separators=(',',':')); FILE.write_text(compact+'\n',encoding='utf-8'); JS_FILE.write_text('window.INVESTOR_TRENDS='+compact+';\n',encoding='utf-8'); print(f'Collected investor trends: {day}'); return 0
    except Exception as exc: print(f'Investor collection failed: {exc}',file=sys.stderr); return 1
if __name__=='__main__': raise SystemExit(main())
