import json,struct,sys
from datetime import datetime,timezone,timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data'/'market.json'; JS_OUT=ROOT/'data'/'market.js'; SEOUL=timezone(timedelta(hours=9))
COLS={0:'date',1:'open',2:'high',3:'low',4:'close',5:'volume',6:'trade_value',7:'open_interest'}

def parse(path):
 data=path.read_bytes(); offset=0; rows={}
 while offset+4<=len(data):
  rid,length=struct.unpack_from('<HH',data,offset); payload=data[offset+4:offset+4+length]; offset+=4+length
  if rid==0x000A:break
  if rid==0x0004 and len(payload)>=8:
   row,col=struct.unpack_from('<HH',payload,0); size=payload[7]; value=payload[8:8+size].decode('cp949',errors='replace'); rows.setdefault(row,{})[col]=value
  elif rid==0x0003 and len(payload)==15:
   row,col=struct.unpack_from('<HH',payload,0); value=struct.unpack_from('<d',payload,7)[0]; rows.setdefault(row,{})[col]=value
 result=[]
 for row in sorted(rows):
  values=rows[row]
  if not isinstance(values.get(0),str):continue
  try: day=datetime.strptime(values[0],'%Y/%m/%d').date()
  except ValueError:continue
  if day.year<2016:continue
  item={name:values.get(col) for col,name in COLS.items()};item['date']=day.isoformat()
  # HTS export 거래대금 단위는 백만원이므로 원 단위로 정규화한다.
  if item.get('trade_value') is not None:item['trade_value']*=1_000_000
  item.update(foreign_spot_net=None,foreign_futures_net=None,source=f'HTS export: {path.name}');result.append(item)
 for i,item in enumerate(result):
  previous=result[i-1]['close'] if i else None
  item['change_pct']=None if not previous else (item['close']/previous-1)*100
 return result

def validate(records):
 errors=[]; dates=[r['date'] for r in records]
 if len(dates)!=len(set(dates)):errors.append('duplicate dates')
 if dates!=sorted(dates):errors.append('dates not ascending')
 for r in records:
  o,h,l,c=(r.get(k) for k in ('open','high','low','close'))
  if None in (o,h,l,c) or h<max(o,l,c) or l>min(o,h,c):errors.append(f"invalid OHLC {r['date']}")
 if errors:raise ValueError('; '.join(errors[:10]))

def main():
 if len(sys.argv)>1:path=Path(sys.argv[1])
 else:
  candidates=list(Path.home().joinpath('Downloads').glob('*코스피*데이터.xls'))
  if not candidates:raise SystemExit('KOSPI xls export not found')
  path=candidates[0]
 records=parse(path);validate(records)
 old=json.loads(OUT.read_text(encoding='utf-8'));flows={r['date']:r for r in old.get('records',[]) if r.get('foreign_spot_net') is not None or r.get('foreign_futures_net') is not None}
 for r in records:
  if r['date'] in flows:
   r['foreign_spot_net']=flows[r['date']].get('foreign_spot_net');r['foreign_futures_net']=flows[r['date']].get('foreign_futures_net')
 old.update(status='live',message='사용자 제공 HTS 일봉 데이터',updated_at=datetime.now(SEOUL).isoformat(timespec='seconds'),sources={'index':f'User-provided {path.name}','foreign_spot':'not_connected','foreign_futures':'not_connected'},records=records)
 compact=json.dumps(old,ensure_ascii=False,separators=(',',':'));OUT.write_text(compact+'\n',encoding='utf-8');JS_OUT.write_text('window.MARKET_DATA='+compact+';\n',encoding='utf-8')
 print(json.dumps({'source':str(path),'rows':len(records),'first':records[0]['date'],'last':records[-1]['date'],'last_close':records[-1]['close'],'last_trade_value':records[-1]['trade_value']},ensure_ascii=False))
if __name__=='__main__':main()
