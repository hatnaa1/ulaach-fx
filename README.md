# ulaach.cc — Монголбанк ба Арилжааны банкны ханшийн Developer API

Монголбанкны 38 валютын өдөр тутмын албан ханш, түүхэн огнооны лавлагаа (`?date=YYYY-MM-DD`), арилжааны банкуудын (Хаан, Голомт, ХХБ) цаг тутмын ханш болон олон хэлний (`MN`, `EN`, `CN`, `JP`, `KR`) бэлэн веб виджет сервис.

- **Вэб болон баримтжуулалт:** [https://ulaach.cc](https://ulaach.cc)
- **OpenAPI / Swagger UI:** [https://ulaach.cc/api/docs](https://ulaach.cc/api/docs)

---

## Гол JSON Endpoint-ууд

| Endpoint | Тайлбар |
|---|---|
| `GET /xansh.json?currency=USD\|EUR\|CNY&lang=MN` | Монголбанкны албан ханш (38 валют, 5 хэлний сонголттой) |
| `GET /xansh.json?date=2026-10-20&currency=USD\|EUR` | Тухайн огнооны Монголбанкны түүхэн албан ханш (амралтын өдөр бол өмнөх ажлын өдрийн хүчинтэй ханш) |
| `GET /banks.json?bank=Khaan\|Golomt\|TDB&currency=USD\|EUR` | Арилжааны банкуудын бэлэн болон бэлэн бус авах/зарах ханш (`?date=YYYY-MM-DD` дэмжинэ) |
| `GET /history.json?currency=USD&days=30` | Валютын сүүлийн `N` хоногийн (эсвэл `start_date`, `end_date`) түүхэн цуваа |
| `GET /xansh.html?currency=USD\|EUR\|CNY&lang=MN&theme=dark&conv_tool=1` | Веб сайтад шигтгэх олон хэлний (`MN`, `EN`, `CN`, `JP`, `KR`) `dark` / `light` IFrame виджет |

---

## Жишээ дуудалт (JavaScript / cURL)

```javascript
const res = await fetch("https://ulaach.cc/xansh.json?currency=USD|EUR&date=2026-10-20&lang=MN");
const rates = await res.json();
console.log(rates);
```

```bash
curl -s "https://ulaach.cc/xansh.json?currency=USD|EUR&date=2026-10-20&lang=MN"
```

---

## Олон хэлний IFrame Виджет (`MN`, `EN`, `CN`, `JP`, `KR`)

```html
<iframe
  style="width:270px;height:360px;border:none;overflow:hidden;border-radius:10px;"
  src="https://ulaach.cc/xansh.html?currency=USD|EUR|CNY|JPY|KRW|RUB&lang=MN&theme=dark&conv_tool=1">
</iframe>
```

---

## Суулгах ба Ажиллуулах (Docker)

1. `.env.example` файлыг `.env` болгон хуулж PostgreSQL унших эрхтэй холболтын мөрийг тохируулна:
   ```bash
   cp .env.example .env
   ```
2. Контейнерийг асаана:
   ```bash
   docker compose up -d --build
   ```
