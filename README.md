# Mini projekat 3: testiran i obezbijeđen API

[![CI](https://github.com/nikolina-milic/mini-projekat-3-api/actions/workflows/ci.yml/badge.svg)](https://github.com/nikolina-milic/mini-projekat-3-api/actions/workflows/ci.yml)

FastAPI servis obračunava cijenu hotelske rezervacije. Projekat ima dva endpointa,
automatizovane testove, provjere kvaliteta i bezbjednosni pregled.

## Endpointi

| Metoda | Putanja | Namjena | Pristup |
| --- | --- | --- | --- |
| `GET` | `/health` | Provjera dostupnosti servisa | Javno |
| `POST` | `/cijena` | Obračun cijene rezervacije | Zaglavlje `X-API-Key` |

`POST /cijena` prihvata od 1 do 30 noćenja, cijenu noćenja veću od 0 i
opcioni popust od 0 do 1. Neočekivana polja se odbijaju. Novčani iznos se računa
pomoću tipa `Decimal` i vraća kao string sa dvije decimale.

Primjer zahtjeva:

```json
{
  "noci": 3,
  "cijena_noci": 80,
  "popust": 0.1
}
```

Odgovor:

```json
{
  "iznos": "216.00",
  "valuta": "EUR"
}
```

## Lokalno pokretanje

Potrebni su Python 3.12 ili noviji i Git.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
$env:PRICE_API_KEY = "unesite-dugacak-nasumican-kljuc"
uvicorn app.main:app --reload
```

Swagger dokumentacija je dostupna na `http://127.0.0.1:8000/docs`.

Primjer poziva iz PowerShella:

```powershell
$headers = @{ "X-API-Key" = $env:PRICE_API_KEY }
$body = @{ noci = 3; cijena_noci = 80; popust = 0.1 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/cijena" `
  -Headers $headers -ContentType "application/json" -Body $body
```

## Testovi i provjere

```powershell
ruff check .
mypy app
pytest
bandit -q -r app
pip-audit -r requirements.txt
```

Testovi obuhvataju ispravne zahtjeve, oba dozvoljena granična broja noćenja,
potpuni popust, decimalno zaokruživanje, neispravne numeričke vrijednosti,
nedostajuća i dodatna polja, pogrešan ili izostavljen API ključ i nedostajuću
serversku konfiguraciju. `pytest` zahtijeva najmanje 95% pokrivenosti granama.

GitHub Actions pokreće `ruff`, `mypy`, `pytest`, `bandit` i `pip-audit` pri svakom
push-u i pull request-u. Workflow ima samo dozvolu za čitanje sadržaja repozitorijuma.

### Rezultati provjera

Provjere su pokrenute 21. novembra 2026:

- `ruff check .`: bez grešaka
- `mypy app`: bez grešaka u tipovima
- `pytest`: 19 testnih slučajeva prolazi, pokrivenost linija i grana je 100%
- `bandit -q -r app`: bez nalaza
- `pip-audit -r requirements.txt`: nema poznatih ranjivosti

Prvi `pip-audit` je pronašao poznate ranjivosti u tranzitivnoj zavisnosti
Starlette 0.50.0. Nalaz je ispravljen nadogradnjom FastAPI-ja sa 0.121.3 na
0.165.0, koja koristi bezbjednu Starlette 1.10.0. Ponovljeni audit nema nalaza.

## Bezbjednosni rizici i mjere

| Rizik | Moguća posljedica | Mjera smanjenja |
| --- | --- | --- |
| Neovlašćen poziv obračuna | Zloupotreba endpointa i trošenje resursa | `/cijena` zahtijeva API ključ, poređenje koristi `secrets.compare_digest`, a tajna se čita iz varijable okruženja |
| Neispravan ili prevelik unos | Pogrešan obračun ili prekomjerno opterećenje | Pydantic ograničava broj noćenja, cijenu i popust; dodatna polja se odbijaju |
| Tajna u repozitorijumu | Krađa API ključa i pristup servisu | Ključ se ne nalazi u kodu; `.env` je ignorisan, a CI/deployment treba da koristi GitHub Secrets ili secret manager |
| Ranjiva zavisnost | Iskorišćavanje poznatog propusta u biblioteci | `pip-audit` provjerava produkcione zavisnosti lokalno i u CI-u |
| Greška zbog binarne aritmetike | Netočan novčani iznos | Obračun koristi `Decimal` i eksplicitno zaokruživanje na dvije decimale |

API ključ je jednostavna autentikacija za nastavni primjer. U produkciji bi trebalo
uvesti HTTPS, rotaciju ključeva, ograničenje broja zahtjeva, evidenciju bez
osjetljivih podataka i korisničku autentikaciju sa odgovarajućim ovlašćenjima.

## Struktura

```text
app/
  __init__.py
  main.py
tests/
  test_api.py
.github/workflows/ci.yml
pyproject.toml
requirements.txt
requirements-dev.txt
.env.example
```


