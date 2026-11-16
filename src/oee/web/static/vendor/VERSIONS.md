# Vendorované frontend knižnice

Stiahnuté 11.11.2026 z jsDelivr (npm balíky) so súhlasom vlastníka (ARCHITECTURE §10.7).
V HTML sa linkujú **iba lokálne** (`/static/vendor/...`) — demo funguje offline. Súbory sa neupravujú.

| Súbor | Balík | Verzia | Licencia | Zdroj | SHA-256 |
|---|---|---|---|---|---|
| `htmx.min.js` | `htmx.org` | 2.0.11 | 0BSD | `https://cdn.jsdelivr.net/npm/htmx.org@2.0.11/dist/htmx.min.js` | `d6fdc75f204e6bdefa99b69bf1e6d4ac69b8a364f77929f45c13476b4000f717` |
| `chart.umd.min.js` | `chart.js` | 4.6.1 | MIT | `https://cdn.jsdelivr.net/npm/chart.js@4.6.1/dist/chart.umd.min.js` | `87364cc2b2a76a6684929e7d6b80b18a897794db38400caff1fcf1791c6925d2` |
| `pico.min.css` | `@picocss/pico` | 2.1.1 | MIT | `https://cdn.jsdelivr.net/npm/@picocss/pico@2.1.1/css/pico.min.css` | `fbc9a63fc9fc9f72d12fd7fc9806e11fa9f77ae4f9cad146b27003a1119ba3db` |

Aktualizácia: stiahnuť novú presnú verziu, prepísať tabuľku (verzia, SHA-256) a spustiť `pytest tests/api`.
