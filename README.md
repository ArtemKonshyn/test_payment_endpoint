# Payment Endpoint

This is the payment part of an online shop that sells physical products. A user pays for their active cart with a saved card.

- **Stack:** Python 3.12, Flask, SQLAlchemy 2, PostgreSQL 16, Celery with Redis, Docker Compose.
- **Endpoint:** `POST /carts/{cart_id}/payments` starts a payment and returns `202 Accepted`. A background worker charges the card.
- **Status:** `GET /payments/{payment_id}` returns the result.
- **Spec:** [`docs/openapi.yaml`](docs/openapi.yaml).

## Run

You need Docker.

```bash
docker compose up --build                # db, redis, migrations, api, worker, beat
docker compose exec api flask seed           # sample users, products, carts and cards
```

The API listens on `http://localhost:8000`. Migrations run automatically in the `migrate` service.

### Try it

There is no login endpoint, because auth is outside this service. Create a token with the CLI instead:

```bash
ALICE=$(docker compose exec -T api flask create-token 11111111-1111-1111-1111-111111111111)

# Start the payment (returns 202 and status "pending")
curl -i -X POST localhost:8000/carts/c1c1c1c1-c1c1-c1c1-c1c1-c1c1c1c1c1c1/payments \
     -H "Authorization: Bearer $ALICE" -H "Idempotency-Key: order-1"

# Read the result (status "succeeded" about a second later)
curl localhost:8000/payments/<id from the Location header> -H "Authorization: Bearer $ALICE"

# Send the same request again: returns 200 and the same payment, with no second charge
curl -i -X POST localhost:8000/carts/c1c1c1c1-c1c1-c1c1-c1c1-c1c1c1c1c1c1/payments \
     -H "Authorization: Bearer $ALICE" -H "Idempotency-Key: order-1"
```

Bob (`22222222-2222-2222-2222-222222222222`) has cart `c2c2c2c2-c2c2-c2c2-c2c2-c2c2c2c2c2c2` and a card that is always declined, so you can see a failed payment.

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

The folder layout follows [microsoft/cookiecutter-python-flask-clean-architecture](https://github.com/microsoft/cookiecutter-python-flask-clean-architecture), an onion architecture. Each layer depends only on the layers inside it. I removed the parts this task does not need: maintenance mode, the service prefix, CORS, and the generic CRUD base classes.

```
src/
  api/              Flask blueprints, marshmallow schemas, JWT, Idempotency-Key header
  services/         PaymentService (API side), PaymentProcessingService (worker side)
  domain/           statuses, exceptions, ports (interfaces of the provider, total service, queue)
  infrastructure/   SQLAlchemy models and repositories, mock provider, Celery tasks
  dependency_container.py   wires everything together (dependency-injector)
migrations/         Alembic: 0001 base schema from the task, 0002 payments
```

The services depend on ports (`src/domain/ports.py`), not on concrete classes. To use a real provider, write a new `PaymentGateway` and change one line in the container.

### Payment flow

```
Client            API (PaymentService)                       Worker (PaymentProcessingService)
  │ POST + Idempotency-Key │                                            │
  │──────────────────────▶ │ BEGIN                                      │
  │                        │  lock cart (SELECT … FOR UPDATE)           │
  │                        │  same key used before? → return that payment (200)
  │                        │  checks: active cart, no live payment,     │
  │                        │          default card, not empty           │
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
| `payment_method_id` stored on the payment | Records which card was charged, even if the default card changes later. |
| `UNIQUE (user_id, idempotency_key)` | One payment per key. Keys are per user, so two users can't collide. |
| Partial unique index on `cart_id` for `pending`, `processing`, `succeeded` | The database itself makes sure a cart can't be paid twice, even if the app has a bug. |
| `CHECK` on `status` and `amount > 0` | Invalid states can't be stored. |
| Partial index on `updated_at` for unfinished payments | Keeps the stale payment sweep fast as the table grows. |
| `provider_charge_id` and `failure_reason` | Needed for reconciliation and support. |

### Response codes of `POST /carts/{cart_id}/payments`

| Code | Meaning |
|---|---|
| 202 | Payment created and queued |
| 200 | Same `Idempotency-Key` sent again. Returns the existing payment |
| 400 | `Idempotency-Key` missing or too long |
| 401 | Token missing or invalid |
| 404 | Cart not found, or it belongs to another user (the response doesn't say which) |
| 409 | Cart is not active, cart already has a live payment, or the key was used for another cart |
| 422 | Empty cart, or the user has no default card |

## Assumptions

- **Auth.** Users log in through another service, which issues HS256 JWTs. The `sub` claim is the user id. `flask create-token` stands in for that service.
- **"Starts the payment"** means the endpoint does not wait for the provider. It returns `202`, and the client polls `GET /payments/{id}`. In production, a provider webhook would complete the payment instead of polling.
- **Total calculation service.** It already exists in the shop. It is mocked as the sum of `quantity × unit_price` over `cart_items` (`SQLCartTotalCalculator`), with no taxes, shipping or discounts.
- **Currency.** All products in a cart have the same currency.
- **Stock** is handled by another part of the shop (for example at order fulfilment), not by the payment.
- **Cart edits.** The cart service must not allow changes while a cart has a `pending` or `processing` payment. The amount is stored on the payment anyway.
- **Card.** The task says each user has a card token, so the payment always charges the user's default card. There is no request body.
- **Mock provider.** The end of the card token decides the result: `…_decline` is declined, `…_unavailable` simulates an outage, and anything else succeeds. The payment id is sent as the provider's idempotency key; a real provider uses it to never charge the same payment twice.
- **Idempotency keys** are kept forever. In production they would expire after about 24 hours, like Stripe's.
- **Retry exhausted.** When the provider stays unavailable, the payment is marked `failed`. With a real provider, it would be reconciled first, because the charge may have gone through.
- The base schema from the task is migration `0001`. Its sample data, plus a cart and a declining card for Bob, is in `sql/seed.sql`.
