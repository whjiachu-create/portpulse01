import datetime as dt
from etl.etl_uncomtrade import run

if __name__ == "__main__":
    today = dt.date.today()
    first_this_month = dt.date(today.year, today.month, 1)
    start = (first_this_month - dt.timedelta(days=365)).replace(day=1)
    # 例：从去年同月到本月（不含本月）之间
    run(start.isoformat(), first_this_month.isoformat())