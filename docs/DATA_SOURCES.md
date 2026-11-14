# Ma'lumot manbalari (tekshirilgan sana: 2026-11-14)

| Manba | Endpoint / kirish | Nima olinadi | Aniqlik va kechikish | Litsenziya / shart | Holat |
|---|---|---|---|---|---|
| NASA POWER Daily | `https://power.larc.nasa.gov/api/temporal/daily/point`, `community=AG`, kalitsiz | T2M, T2M_MAX/MIN, PRECTOTCORR, RH2M, WS2M, ALLSKY_SFC_SW_DWN (MJ/m²/kun), GWETTOP/GWETROOT (0–1) | meteo ½°×⅝° (~50 km), quyosh 1°×1°; kechikish meteo 2–3 kun, quyosh 5–7 kun. `fill_value=-999` | NASA ochiq ma'lumot | ✅ jonli tekshirilgan |
| NASA POWER iqlim tarixi | o'sha endpoint, 1981-01-01 → o'tgan yil oxiri (4 parametr, bitta so'rov ~3 s) | yillik agregatlar, 1991–2020 oylik baza | o'sha | o'sha | ✅ |
| Open-Meteo Forecast | `https://api.open-meteo.com/v1/forecast`, kalitsiz, `wind_speed_unit=ms`, `past_days=7` | soatlik/kunlik: harorat, namlik, yog'in, ehtimol, qor, shamol, radiatsiya, ET0 (FAO), tuproq harorati/namligi (model), weather_code | model grid, 7 kun prognoz | notijorat: <10 000 so'rov/kun, CC BY 4.0; tijoriy bosqichda pullik tarif | ✅ jonli tekshirilgan |
| NASA EONET v3 | `https://eonet.gsfc.nasa.gov/api/v3/events?bbox=minLon,maxLat,maxLon,minLat` | tabiiy hodisalar | hodisa bo'yicha | ochiq | ✅ adapter yozilgan (`integrations/eonet.py`), UI'ga ulanmagan (P1) |
| Claude API | `anthropic` Python SDK, `claude-opus-5-5` (`AI_MODEL`) | tavsiyalarni soddalashtirish, AI agronom chat (tool use) | — | pullik (≈$4/$20 1M token, 2026-09 holati — tekshiring) | ⚠️ kalitsiz rejimda sinaldi |
| Esri World Imagery | Leaflet tile qatlami | sun'iy yo'ldosh fon xaritasi | — | atributsiya bilan; tijoriy foydalanish shartlarini tekshiring | ✅ |
| Google Maps JS + Terra Draw | `VITE_MAP_PROVIDER=google` | sun'iy yo'ldosh xarita | — | Google billing hisobi kerak; Drawing Library 2026-may'dan mavjud emas → Terra Draw | ⚠️ yaroqli kalit bilan sinalmagan |
| NASA HLS v2.0 (HLSL30/HLSS30, VI) | Earthdata Login + `earthaccess` yoki AppEEARS | 30 m NDVI/EVI | 2–3 kunda | Earthdata hisobi | ❌ P1 — hali qilinmagan |
| SMAP L3/L4 | AppEEARS / earthaccess | tuproq namligi | 9 km | Earthdata | ❌ P2 |
| USDA Crop-CASMA | — | — | faqat AQSh (CONUS) | — | ❌ O'zbekiston uchun yaroqsiz |

## Talqin qoidalari (kodda amalga oshirilgan)
- POWER/SMAP qiymatlari UI'da "~50 km grid katagi (hudud foni)" deb belgilanadi — dala nuqtasi sifatida ko'rsatilmaydi.
- `GWETTOP/GWETROOT` — tuproq g'ovaklarining to'lganlik ulushi (0–1), sensorning hajmiy namligi (%) bilan to'g'ridan-to'g'ri solishtirilmaydi.
- "Hozir" — sensor + prognoz; "o'tmish/iqlim" — POWER. POWER kechikishi Open-Meteo `past_days` bilan to'ldiriladi.
- Bir grid katagidagi dalalar POWER keshini bo'lishadi (`weather_observations.grid_key`).

## Agronomik konstantalar
`knowledge/crops.yaml` va `knowledge/soils.yaml` — har bir qiymat manbasi bilan: FAO-56 (Kc, bosqichlar, Zr, p, tuproq), FAO-33 (Ky), FAO-29 (ECe chegarasi), FAO Crop Water Information (mavsumiy suv talabi). "GEN" (umumiy agronomik qiymat) va "REGION" (mintaqaviy hosil) belgilari — **tekshirilmagan**, UI va AI'da taxmin sifatida ko'rsatiladi; mahalliy agronom/FAOSTAT bilan tasdiqlash kerak. Mosh FAO jadvallarida yo'q — "quruq loviya" proksi sifatida olingan.
