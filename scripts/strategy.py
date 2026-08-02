BUY_PLAN=[(3_000_000,5900),(3_000_000,5500),(4_000_000,5300)]
SELL_PLAN=[(.30,6500),(.30,6800),(.40,7050)]
def simulate(buys=BUY_PLAN,exit_level=None):
    invested=sum(a for a,_ in buys); units=sum(a/p for a,p in buys)
    exit_level=exit_level or sum(r*p for r,p in SELL_PLAN); profit=units*exit_level-invested
    return {"average_entry":invested/units,"profit":profit,"return_pct":profit/invested*100}
def classify(close,spot=None,futures=None):
    if close<5100 and spot is not None and spot<0 and futures is not None and futures<0:return "손절 경보"
    if close>=6950:return "3차 매도권"
    if 6750<=close<=6850:return "2차 매도권"
    if 6450<=close<=6550:return "1차 매도권"
    if 5850<=close<=5950:return "1차 매수권"
    if 5450<=close<=5550:return "2차 매수권"
    if 5200<=close<5400 and spot is not None and spot>0 and futures is not None and futures>0:return "반전 확인 후보"
    return "관망"

