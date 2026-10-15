# secomat (Krüger) for Home Assistant

[![Validate](https://github.com/gmb2012/ha-secomat/actions/workflows/validate.yml/badge.svg)](https://github.com/gmb2012/ha-secomat/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories/)

> Runs in the author's home since October 2026 (secomat 2, firmware 0.3.06). The meaning of the
> device's state codes was kindly provided by Krüger ([#1](https://github.com/gmb2012/ha-secomat/issues/1)).

Unofficial Home Assistant integration for the **Krüger secomat 2** laundry dryer / room dehumidifier.
It polls the same cloud API that the official secomat app uses (every 60 s) and sends the same commands.
According to Krüger the protocol is the same for the secomat 2, 4, 6 and 8, so those should work too;
only the secomat 2 has been tested.

> **Disclaimer:** This project is not affiliated with, endorsed by or supported by Krüger + Co. AG.
> "secomat" and "Krüger" are trademarks of their respective owners. The API is undocumented and may
> change at any time. Use at your own risk.

*Deutsch weiter unten.*

## Installation (HACS custom repository)

1. HACS → three-dot menu → **Custom repositories**
2. Add `https://github.com/gmb2012/ha-secomat`, category **Integration**
3. Install **secomat (Krüger)**, restart Home Assistant
4. Settings → Devices & services → **Add integration** → *secomat (Krüger)*, enter the claim token

## Reading the claim token

The secomat has no user account; the app authenticates with a per-device **claim token** that it
reads once via Bluetooth LE. `tools/read_token.py` does the same:

```bash
pip install bleak
python tools/read_token.py            # --timeout 20 (seconds) by default
```

Run it on a computer in Bluetooth range of the secomat. If the device is not found, close the app on
phones/tablets nearby and press the WLAN button on the secomat (pairing mode), then retry. The script
only prints token and id to the terminal and writes nothing to disk. **Treat the token like a
password** and do not post it anywhere.

## Entities

| Entity | Description |
|---|---|
| Sensor *Temperature*, *Humidity* | Room climate measured by the secomat |
| Sensor *Operating state* | Off / Auto / Manual on |
| Sensor *Status* | Ready / Drying / Finished (laundry dry, waiting to be taken out) / Aborted / Error; raw code in the attribute `code` |
| Sensor *Next start* | Scheduled start of laundry drying |
| Sensor *Errors* | Number of active errors, texts in the attribute `errors` |
| Sensor *Firmware*, *Data age* | Diagnostics |
| Binary sensor *Problem* | On while any error is active or the device is in its error state |
| Switch *Room drying* | 24 h room drying |
| Switch *Display backlight*, *Lock drying level* | Configuration |
| Select *Operating mode* | Off / Auto / Manual on |
| Select *Drying level* | Very dry / Dry / Medium / Damp |
| Button *Start drying*, *Stop drying* | Start or stop laundry drying now |

Action `secomat.start_at` (`config_entry_id`, `start`): schedules laundry drying to start at a given
time; times in the past start immediately.

## Deutsch

Inoffizielle Home-Assistant-Integration für den **Krüger secomat 2**. Sie fragt alle 60 s dieselbe
Cloud-API ab wie die offizielle App. **Kein Zusammenhang mit Krüger + Co. AG**, keine Unterstützung
durch den Hersteller; die API ist nicht dokumentiert und kann sich jederzeit ändern. Laut Krüger ist
das Protokoll für secomat 2, 4, 6 und 8 gleich; getestet ist nur der secomat 2. Die Bedeutung der Statuscodes hat Krüger
freundlicherweise erklärt ([#1](https://github.com/gmb2012/ha-secomat/issues/1)); *Fertig* heisst: Wäsche
trocken, Gerät wartet auf die Entnahme.

- **Installation:** HACS → *Benutzerdefinierte Repositories* → URL dieses Repos, Kategorie
  *Integration* → *secomat (Krüger)* installieren → HA neu starten → Integration hinzufügen,
  Claim-Token eingeben.
- **Token auslesen:** `pip install bleak`, dann `python tools/read_token.py` auf einem Rechner in
  Bluetooth-Reichweite. Wird kein Gerät gefunden: App auf Handy/Tablet schliessen, WLAN-Taste am
  secomat drücken (Kopplungsmodus) und erneut versuchen. Der Token wird nur im Terminal ausgegeben;
  wie ein Passwort behandeln.
- **Entitäten:** Temperatur, Luftfeuchtigkeit, Betriebszustand, Nächster Start, Fehler (Anzahl +
  Texte), Firmware, Datenalter, Problem, Raumtrocknung, Display-Beleuchtung, Trocknungsstufe sperren,
  Betriebsart, Trocknungsstufe, Trocknung starten/stoppen; Aktion `secomat.start_at`.

## Development

```bash
pip install -r requirements_test.txt
ruff check .
pytest --cov=custom_components/secomat
```

## License

MIT, see [LICENSE](LICENSE).
