#!/usr/bin/env python3
import os, sys, json, urllib.parse, urllib.request, time, datetime, hashlib, pathlib
API=os.getenv("COMTRADE_TOKEN","")  # 可为空；为空则使用匿名配额（更慢/更严）
BASE="https://comtrade.un.org/api/get"
def fetch(code, frm, to, months=6):
    # period: 最近 months 个自然月（yyyymm）
    today=datetime.date.today().replace(day=1)
    periods=[(today - datetime.timedelta(days=30*i)).strftime("%Y%m") for i in range(months,0,-1)]
    out=[]
    for p in periods:
        q={"max":"5000","type":"C","freq":"M","px":"HS","ps":p,"r":to,"p":frm,"rg":"1","cc":code,"fmt":"JSON"}
        if API: q["token"]=API
        url=f"{BASE}?{urllib.parse.urlencode(q)}"
        with urllib.request.urlopen(url, timeout=30) as r: data=json.load(r)
        rows = (data.get("dataset") or [])
        v = sum(int(x.get("TradeValue",0) or 0) for x in rows) if rows else 0
        out.append({"month":f"{p[:4]}-{p[4:]}-01","value":v,"src":"comtrade"})
        time.sleep(1.2)  # 轻限流，避免被踢
    return {"code":code,"frm":frm,"to":to,"points":out}

if __name__=="__main__":
    code=sys.argv[1] if len(sys.argv)>1 else "8401"
    frm =sys.argv[2] if len(sys.argv)>2 else "CN"
    to  =sys.argv[3] if len(sys.argv)>3 else "US"
    months=int(sys.argv[4]) if len(sys.argv)>4 else 6
    d=fetch(code,frm,to,months)
    pathlib.Path("data/hs").mkdir(parents=True, exist_ok=True)
    fp=f"data/hs/{code}_{frm}_{to}_{months}.json"
    open(fp,"w",encoding="utf-8").write(json.dumps(d,ensure_ascii=False))
    print(fp)
