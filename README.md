# Payment Endpoint

This is the payment part of an online shop that sells physical products. A user pays for their active cart with their saved card.

- **Stack:** Python 3.12, Flask, SQLAlchemy 2, PostgreSQL 16, Celery with Redis, Docker Compose.
- **Endpoint:** `POST /payments` starts the payment for the user's active cart and returns `202 Accepted`. A background worker charges the card.
- **Status:** `GET /payments/{payment_id}` returns the result.
- **Docs:** Swagger UI at http://localhost:8000/docs, spec in [`docs/openapi.yaml`](docs/openapi.yaml).

## Run

You need Docker.

Start the stack. It runs in the foreground and shows the logs; press Ctrl+C to stop it.

```bash
docker compose up --build    # db, redis, migrations, api, worker, beat
```

In a second terminal, load the sample data. Do this once per fresh database: the rows have fixed ids, so a second run fails. Run `docker compose down -v` to start over.

```bash
docker compose exec api flask seed    # sample users, products, carts and cards
```

The API listens on `http://localhost:8000`, with Swagger UI at http://localhost:8000/docs. Migrations run automatically in the `migrate` service.

### Sample data

| User | User id | Cart | Card |
|---|---|---|---|
| Alice | `11111111-1111-1111-1111-111111111111` | Blue Kettle + 2 × Ceramic Mug = 70.00 USD | always succeeds |
| Bob | `22222222-2222-2222-2222-222222222222` | Wool Blanket = 89.99 USD | always declined |

Each cart can be paid only once. After that, the user has no active cart and `POST /payments` answers `404`. Run `docker compose down -v` and the steps above to start over.

### Get a token

There is no login endpoint, because auth is outside this service. Create a JWT for a user with the CLI. It is valid for 1 hour.

```bash
docker compose exec -T api flask create-token 11111111-1111-1111-1111-111111111111
```

The token is the long string that starts with `eyJ`. Copy it as one line, with no spaces or line breaks. The user id itself is not a token: sending it returns `401 Not enough segments`.

### Try it in Swagger UI

1. Open http://localhost:8000/docs and click **Authorize**.
2. Paste the token only, without `Bearer ` and without spaces (Swagger UI adds the `Bearer` prefix). Click **Authorize**, then **Close**.
3. `POST /payments` → **Try it out** → set `Idempotency-Key` to any string, for example `order-1` → **Execute**. The response is `202` with `"status": "pending"`.
4. `GET /payments/{payment_id}` → **Try it out** → replace Swagger's example id (`3fa85f64-…`) with the `id` from step 3 → **Execute**. The status is `succeeded` (or `failed` for Bob) about a second later.
5. Run step 3 again with the same key: `200` and the same payment, with no second charge.

To switch users, click **Authorize**, then **Logout**, and paste the other user's token.

### Try it with curl

The block can be pasted as is (it needs curl 7.84 or newer for `%header{location}`):

```bash
ALICE=$(docker compose exec -T api flask create-token 11111111-1111-1111-1111-111111111111)

# Start the payment and keep the payment URL from the Location header (the response is 202)
PAYMENT_URL=$(curl -s -o /dev/null -w '%header{location}' \
     -X POST localhost:8000/payments \
     -H "Authorization: Bearer $ALICE" -H "Idempotency-Key: order-1")

# Read the payment: "pending" at first, "succeeded" about a second later
curl "localhost:8000$PAYMENT_URL" -H "Authorization: Bearer $ALICE"

# Send the same request again: returns 200 and the same payment, with no second charge
curl -i -X POST localhost:8000/payments \
     -H "Authorization: Bearer $ALICE" -H "Idempotency-Key: order-1"
```

For a failed payment, run the same steps with Bob's user id.

## Tests

```bash
docker compose --profile test run --rm tests
```

The tests run against a real PostgreSQL database (`payments_test`, created when the db container starts for the first time). They cover:

- Every response code of the endpoint.
- Idempotency, including concurrent requests.
- The worker: success, decline, provider outage with retries, and the stale payment sweep.

To run them without the test container, start the database with `docker compose up -d db` and then run `pip install -r requirements-test.txt && pytest`.

## Architecture

The folder layout follows [microsoft/cookiecutter-python-flask-clean-architecture](https://github.com/microsoft/cookiecutter-python-flask-clean-architecture), an onion architecture. Each layer depends only on the layers inside it.

```
src/
  api/              Flask blueprints, marshmallow schemas, JWT, Idempotency-Key header, Swagger UI
  services/         PaymentService (API side), PaymentProcessingService (worker side)
  domain/           statuses, exceptions, ports (interfaces of the provider, total service, queue)
  infrastructure/   SQLAlchemy models and repositories, mock provider, Celery tasks
  dependency_container.py   wires everything together (dependency-injector)
migrations/         Alembic: 0001 base schema from the task, 0002 payments
docs/               openapi.yaml and the Swagger UI page served at /docs
```

Main business logic files:

| File | What it does |
|---|---|
| `src/api/controllers/payment.py` | `POST /payments` and `GET /payments/{payment_id}` |
| `src/services/payment_service.py` | Starts a payment: idempotency check, active cart lock, validation, `pending` payment, enqueue |
| `src/services/payment_processing_service.py` | Charges the card in the worker and sets the result: `succeeded` + cart `checked_out`, or `failed` |
| `src/infrastructure/tasks/payment_tasks.py` | Celery tasks: `process_payment` with retries, `requeue_stale_payments` for the recovery sweep |
| `src/infrastructure/repositories/payment_repository.py` | Payment queries: idempotency key lookup, live payment check, row locks, stale payments |
| `src/infrastructure/repositories/cart_repository.py` | Locks the user's active cart (`SELECT … FOR UPDATE`) |
| `src/domain/constants.py` | Payment and cart statuses, stale payment age |
| `src/domain/ports.py` | Interfaces of the payment provider, the total calculation service and the job queue |
| `migrations/versions/0002_payments.py` | The `payments` table, its constraints and indexes |

The services depend on ports (`src/domain/ports.py`), not on concrete classes. `src/dependency_container.py` picks the implementation for each port:

| Port | What it is | Implementation |
|---|---|---|
| `PaymentGateway` | the external payment provider | `MockPaymentGateway` |
| `CartTotalCalculator` | the shop's existing total calculation service | `SQLCartTotalCalculator` (mock) |
| `PaymentTaskQueue` | the background job queue | `CeleryPaymentTaskQueue` |

To use a real provider, write a new `PaymentGateway` and change one line in the container.

### Payment flow

```
Client            API (PaymentService)                       Worker (PaymentProcessingService)
  │ POST + Idempotency-Key │                                            │
  │──────────────────────▶ │ BEGIN                                      │
  │                        │  same key used before? → return that payment (200)
  │                        │  lock the user's active cart (FOR UPDATE)  │
  │                        │  check the key again under the lock        │
  │                        │  checks: no live payment, card, not empty  │
  │                        │  INSERT payment 'pending'                  │
  │                        │ COMMIT                                     │
  │                        │ enqueue(payment_id) ──────────────────────▶│ tx: lock payment, set 'processing'
  │ ◀──── 202 + Location ──│                                            │ charge card (no open transaction,
  │                        │                                            │   idempotency key = payment id)
  │ GET /payments/{id} ───▶│                                            │ tx: 'succeeded' + cart 'checked_out'
  │ ◀──── status ──────────│                                            │  or 'failed' + failure_reason
```

- **The payment is saved before it is queued.** If Redis is down, or a worker dies, the Celery beat job `requeue_stale_payments` re-queues every `pending` or `processing` payment that has not been updated for 2 minutes.
- **Every worker step is idempotent.** Finished payments are skipped, and the provider gets the payment id as its idempotency key. A payment that is queued twice never charges the card twice.
- **Retries:** if the provider is unavailable, the task retries 5 times with exponential backoff (1, 2, 4, 8, 16 seconds). After that, the payment is marked `failed`.
- **No database transaction is open during the call to the provider.** A slow provider does not hold row locks.

### Schema (`migrations/versions/0002_payments.py`)

| Item | Why |
|---|---|
| `payments` table, one row per payment attempt | A failed attempt stays as history. The user retries with a new Idempotency-Key, which creates a new row. |
| `amount` and `currency` stored on the payment | Snapshot of what was charged, even if prices change later. |
| `payment_method_id` stored on the payment | Records which card was charged, even if the user's card changes later. |
| `UNIQUE (user_id, idempotency_key)` | One payment per key. Keys are per user, so two users can't collide. |
| Partial unique index on `cart_id` for `pending`, `processing`, `succeeded` | The database itself makes sure a cart can't be paid twice, even if the app has a bug. |
| `CHECK` on `status` and `amount > 0` | Invalid states can't be stored. |
| Partial index on `updated_at` for unfinished payments | Keeps the stale payment sweep fast as the table grows. |
| `provider_charge_id` and `failure_reason` | Needed for reconciliation and support. |

### Response codes of `POST /payments`

| Code | Meaning |
|---|---|
| 202 | Payment created and queued |
| 200 | Same `Idempotency-Key` sent again. Returns the existing payment |
| 400 | `Idempotency-Key` missing or too long |
| 401 | Token missing or invalid |
| 404 | The user has no active cart |
| 409 | A payment for the active cart is already in progress |
| 422 | Empty cart, or the user has no card |

## Assumptions

- **Auth.** Users log in through another service, which issues HS256 JWTs. The `sub` claim is the user id. `flask create-token` stands in for that service.
- **"Starts the payment"** means the endpoint does not wait for the provider. It returns `202`, and the client polls `GET /payments/{id}`. In production, a provider webhook would complete the payment instead of polling.
- **Total calculation service.** It already exists in the shop. It is mocked as the sum of `quantity × unit_price` over `cart_items` (`SQLCartTotalCalculator`), with no taxes, shipping or discounts.
- **Currency.** All products in a cart have the same currency.
- **Stock** is handled by another part of the shop (for example at order fulfilment), not by the payment.
- **Cart edits.** The cart service must not allow changes while a cart has a `pending` or `processing` payment. The amount is stored on the payment anyway.
- **Cart.** A user has one active cart at a time (as the base schema says), so the endpoint pays that cart and takes no cart id.
- **Order.** A production shop would first turn the cart into an order: a fixed record of the items, prices and total that keeps the purchase history and is what gets paid. The task has no orders table and says the user pays for the cart, so the payment points to the cart and stores the amount it charged.
- **Card.** Each user has exactly one card token, so the payment always charges it. There is no request body.
- **Mock provider.** The end of the card token decides the result: `…_decline` is declined, `…_unavailable` simulates an outage, and anything else succeeds. The payment id is sent as the provider's idempotency key; a real provider uses it to never charge the same payment twice.
- **Idempotency keys** are kept forever. In production they would expire after about 24 hours, like Stripe's.
- **Retry exhausted.** When the provider stays unavailable, the payment is marked `failed`. With a real provider, it would be reconciled first, because the charge may have gone through.
- The base schema from the task is migration `0001`. Its sample data, plus a cart and a declining card for Bob, is in `sql/seed.sql`.
