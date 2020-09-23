# Currency Exchange Rates API 

Currency Exchnage Rates API is a free service for current and historical foreign exchange rates [published by the European Central Bank](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html).

## Local Installation and Execution steps

- Run `pipenv shell`
- Run `pipenv run`

#### Lates & specific date rates
Get the latest foreign exchange rates.

```http
GET /latest
```

Get historical rates other than latest..

```http
GET /2020-08-26
```

Rates are quoted against the Euro by default. Quote against a different currency by setting the base parameter in your request.

```http
GET /latest?base=USD
```

Get exchange rate using a different base currency

```http
GET /2020-08-26?base=USD
```