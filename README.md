# 🛒 Product Importer — FastAPI · Celery · PostgreSQL · Redis

A scalable web application for **bulk product import & management**, built as part of the SDE-1 assignment for **Fulfil**.


---

## ✨ Features

| Feature | Status |
|--------|--------|
| Upload CSV up to **500,000 products** | ✅ |
| Real-time upload progress using **SSE** | ✅ |
| Handles **duplicate SKUs (case-insensitive)** | ✅ |
| Paginated + filterable Product Management UI | ✅ |
| Create / Update / Delete products | ✅ |
| **Bulk delete** with confirmation | ✅ |
| Full **Webhook management** (add / update / enable / disable / delete) | ✅ |
| **Test webhook** with latency + HTTP status feedback | ✅ |
| Fully async using **Celery & Redis** | ✅ |

---

## 🏗️ Tech Stack

| Category | Technology |
|---------|-------------|
| Web framework | FastAPI |
| Async background execution | Celery |
| Message broker | Redis |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Frontend | HTML + Vanilla JS |
| Deployment | Render + Docker |

---

## 🔥 Architecture Overview

```

CSV Upload → FastAPI → Save Temp File → Celery Task
↓ progress via Redis
UI listens via SSE (EventSource)
┌───────────────────┐
│ Celery Worker     │
│ COPY → staging    │
│ dedupe by SKU     │
│ UPSERT → products │
└───────────────────┘

```

Webhook flow:

```

User adds webhook → stored in DB
Webhook test → POST request sent to target URL → show status + latency

````

---

## 📦 Local Development

### 1️⃣ Clone repository
```bash
git clone https://github.com/<your-username>/product-importer-fastapi
cd product-importer-fastapi
````

### 2️⃣ Start full stack

```bash
docker compose up --build
```

Services:

* Web → [http://localhost:8000](http://localhost:8000)
* Redis → redis://localhost:6379
* PostgreSQL → postgres://localhost:5432

---

## 🧪 Sample CSV

```
sku,name,description,price
SKU001,Product 1,First test product,9.99
SKU002,Product 2,Second test product,19.99
sku001,Product 1 updated,Duplicate should update,11.99
```

---

## 📍 API Endpoints

### Products

| Method | Endpoint             | Description                 |
| ------ | -------------------- | --------------------------- |
| GET    | `/api/products`      | List + pagination + filters |
| POST   | `/api/products`      | Create product              |
| PUT    | `/api/products/{id}` | Update product              |
| DELETE | `/api/products/{id}` | Delete one                  |
| DELETE | `/api/products`      | Bulk delete                 |

### Webhooks

| Method | Endpoint                  |
| ------ | ------------------------- |
| GET    | `/api/webhooks`           |
| POST   | `/api/webhooks`           |
| PUT    | `/api/webhooks/{id}`      |
| DELETE | `/api/webhooks/{id}`      |
| POST   | `/api/webhooks/test/{id}` |

---

## 🤖 AI Tools Used

This project intentionally uses AI as a productivity multiplier:

| AI Tool        | Usage                                                   |
| -------------- | ------------------------------------------------------- |
| ChatGPT        | Architecture discussions & SQL COPY+UPSERT optimization |
| GitHub Copilot | UI refinements & refactoring                            |
| Cursor IDE     | Auto-fixing repetitive boilerplate                      |

AI helped speed up execution — but every generated block was **validated & customized** manually for correctness and performance.

---

## 📌 Scaling Notes

* COPY + UPSERT is O(n) and capable of **500k+ row imports**
* No request timeout — long import runs in **Celery**, UI updates through **SSE**
* All DB writes batched for performance
* Webhooks run async to avoid blocking UI

---

## 🧑‍💻 Author

**Virendar**
Full-Stack Python Engineer
🔗 LinkedIn / GitHub: <your links>
