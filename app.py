import pymongo
import requests
import os

from datetime import datetime
from xml.etree import ElementTree
from sanic import Sanic
from sanic.response import json
from bson.json_util import dumps, loads

from apscheduler.schedulers.asyncio import AsyncIOScheduler

app = Sanic("Currency Exchange API")
refreshDates = []

# Base Currency is EUR from European Central Bank
baseCurrency = "EUR"

# Initialize the Mongo DB connection and get the document collection
dbClient = pymongo.MongoClient(os.environ.get("DB_URL"))
fxDB = dbClient["currency-exchange"]
fxRates = fxDB["fxrates"]

namespaces = {
    "gesmes": "http://www.gesmes.org/xml/2002-08-01",
    "eurofxref": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref",
}


async def update_rates():
    print("Start FX Rate Updates...")

    r = requests.get(os.environ.get("ECB_RATES_URL"))
    envelope = ElementTree.fromstring(r.content)

    # Get all the dates stored in the FX Rates Collection
    result = fxRates.find({}, {"_id": 0, "date": 1})
    datecoll = []
    for r in result:
        datecoll.append(r["date"])

    data = envelope.findall("./eurofxref:Cube/eurofxref:Cube[@time]", namespaces)
    for d in data:
        date = d.attrib["time"]
        refreshDates.append(date)
        # Insert record for the date not found in date list
        if not date in datecoll:
            rates = {
                "date": d.attrib["time"],
                "rates": {
                    c.attrib["currency"]: float(c.attrib["rate"]) for c in list(d)
                },
            }
            fxRates.insert_one(rates)

    print("End FX Rate Updates...")


@app.listener("before_server_start")
async def initialize_scheduler(app, loop):
    try:
        scheduler = AsyncIOScheduler()
        scheduler.start()
        scheduler.add_job(update_rates, "interval", minutes=20)
    except BlockingIOError:
        pass


@app.route("/")
async def index(request):
    return json({"message": "Welcome of FX Rate API."})

@app.route("/latest", methods=["GET"])
@app.route("/<fxdate>", methods=["GET"])
async def fxrates(request, fxdate=None):
    if "base" in request.args and request.args["base"][0] != "EUR":
        baseCurrency = request.args["base"][0]
    else:
        # Base Currency is EUR from European Central Bank
        baseCurrency = "EUR"

    fx_rate = None

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

        fx_rate = fxRates.find_one(
            {"date": dt.strftime("%Y-%m-%d")}, {"_id": 0, "date": 1, "rates": 1}
        )        
    else:
        latestRate = fxRates.find({}, {"_id": 0, "date": 1, "rates": 1}).sort('date', -1).limit(1)
        dumpJson = dumps(latestRate)
        fx_rate = loads(dumpJson[1:len(dumpJson) - 1])

    if baseCurrency == "EUR":
        rates = fx_rate["rates"]
        rates["EUR"] = round(1, 4)
        return json({ "base": baseCurrency, "date": fx_rate["date"], "rates": rates})
    
    if fx_rate:                        
        rates = fx_rate['rates']
        
        if baseCurrency in rates:
            base_rate = round(rates[baseCurrency], 4)
            rates = {
                currency: round(rate / base_rate, 4) for currency, rate in rates.items()
            }
            rates["EUR"] = round(1 / base_rate, 4)

            return json({"base": baseCurrency, "date": fx_rate["date"], "fxrates": rates})
        else:
            return json(
                {"error": "Base '{}' is not supported.".format(base)}, status=400
            )                
    else:
        return json(
            {"error": "There is no data for date '{}'".format(dt)},
            status=400,
        )

@app.route("/refresh", methods=["GET"])
async def refreshRates(request):
    await update_rates()
    return json(refreshDates)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)