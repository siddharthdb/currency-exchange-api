import pymongo
import requests
import os

from datetime import datetime
from xml.etree import ElementTree
from sanic import Sanic
from sanic.response import json
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

app = Sanic("FX Rates API")

myclient = pymongo.MongoClient(os.environ.get('DB_URL'))
mydb = myclient["currency-exchange"]
mycol = mydb["fxrates"]

namespaces = {
    "gesmes": "http://www.gesmes.org/xml/2002-08-01",
    "eurofxref": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref",
}

async def update_rates():
    print("Start FX Rate Updates...")
    r = requests.get(os.environ.get('ECB_RATES_URL'))
    envelope = ElementTree.fromstring(r.content)

    result = mycol.find({},{ "_id": 0, "date": 1 })
    datecoll = []
    for r in result:
        datecoll.append(r['date'])

    data = envelope.findall("./eurofxref:Cube/eurofxref:Cube[@time]", namespaces)
    for d in data:
        date = d.attrib["time"]
        if not date in datecoll:
            rates = {
                "date": d.attrib["time"],
                "rates": {
                    c.attrib["currency"]: float(c.attrib["rate"]) for c in list(d)
                }
            }
            mycol.insert_one(rates)
    print("End FX Rate Updates...")

@app.listener("before_server_start")
async def initialize_scheduler(app, loop):
    try:
        scheduler = AsyncIOScheduler()
        scheduler.start()
        scheduler.add_job(update_rates, "interval", minutes=30)
    except BlockingIOError:
        pass


@app.route("/")
async def index(request):
    return json({"message": "Welcome of FX Rate API."})

@app.route("/latest", methods=["GET"])
@app.route("/<fxdate>", methods=["GET"])
async def fxrates(request, fxdate=None):
    if fxdate:
        try:
            dt = datetime.strptime(fxdate, "%Y-%m-%d")
        except ValueError as e:
            return json({"error": "{}".format(e)}, status=400)

        if dt < datetime(1999, 1, 4):
            return json(
                {"error": "There is no data for dates older then 1999-01-04."},
                status=400,
            )

        fx_rate = mycol.find_one({ "date": dt.strftime("%Y-%m-%d")}, { "_id": 0, "date": 1, "rates": 1 })
        if fx_rate:
            return json(fx_rate)
    else:
        x = mycol.find_one()
        return json(
            { "base": "EUR", "date": x["date"], "rates": x["rates"] }
        )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, workers=4)