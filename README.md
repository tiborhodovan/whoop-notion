# WHOOP -> Notion automata szinkron

Ez a repo minden nap automatikusan atmasolja a WHOOP adataidat (recovery, sleep, cycle, workout)
a Notion adatbazisaidba, a GitHub Actions szolgaltatas segitsegevel - a te gepedet nem kell hozza bekapcsolni.

## Hogyan mukodik

- Minden nap 06:00 UTC-kor (08:00 CEST) a GitHub automatikusan lefuttatja a sync_all.py scriptet.
- A script lekeri a friss WHOOP adatokat, es beirja / frissiti a Notion adatbazisokban.
- A WHOOP hozzaferes token (refresh token) automatikusan frissul minden futas utan.

## Manualis inditas

A repo "Actions" fulen a workflow neve mellett a "Run workflow" gombbal barmikor
elinditathato kezzel is, nem kell megvarni a napi automatikus futast.
