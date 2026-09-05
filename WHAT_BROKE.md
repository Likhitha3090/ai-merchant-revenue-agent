What Broke — and How I Fixed It
This document covers the three most significant technical failures I hit while building the AI Merchant Revenue Agent, how I diagnosed each one, and what I changed as a result.
---
1. Groq model returning 404
What broke:
Early in development, calls to the Groq API for AI intent parsing and recommendation started failing with a 404 error. The agent couldn't process any customer request.
Cause:
The specific model identifier I had hardcoded was no longer a valid/supported model on Groq's endpoint. I had picked it early on without checking whether it was still active.
How I found it:
I logged the raw API response instead of just catching the exception, which surfaced the 404 and the model name in the error body — that made it obvious it was a model availability issue rather than an auth or network problem.
Fix:
I switched to a currently supported model (the OpenAI GPT OSS model served through Groq, as referenced in the tech stack) and added a basic startup check that calls the model once and fails loudly if it's unreachable, rather than only failing silently mid-request later.
What I learned:
Don't hardcode a model name and assume it's permanent — model availability on third-party inference APIs changes, so it's worth verifying at startup rather than discovering it during a live demo.
---
2. PostgreSQL connection string breaking on a special character
What broke:
The backend couldn't connect to PostgreSQL. SQLAlchemy was raising connection errors that didn't clearly point to the actual cause.
Cause:
My database password contained an `@` character. Since the DB URL was being built as a single connection string (`postgresql://user:password@host:port/dbname`), the `@` inside the password was being interpreted as the separator between credentials and host — so the URL was parsed incorrectly and pointed at the wrong "host."
How I found it:
I printed the constructed connection string during debugging (with the password redacted) and noticed the host portion looked wrong — it included part of what should have been the password.
Fix:
I separated the database credentials into individual environment variables (`DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`) instead of one pre-built URL, and constructed/escaped the connection string in code rather than by hand. This is reflected in the `.env` structure documented in the README.
What I learned:
Never hand-assemble a URL-style connection string from raw credentials — special characters need proper encoding, and it's safer to keep credentials as separate config values and let the driver/library build the connection string.
---
3. Payment retry and cancellation flow was unreliable
What broke:
When a customer cancelled a Razorpay checkout or a payment failed, the retry option sometimes didn't appear correctly on the frontend, and the browser console showed JavaScript errors. In some cases the UI state didn't clearly reflect that the order was still pending rather than paid.
Cause:
The frontend was handling checkout cancellation and payment failure as something close to an afterthought — the success path was well-handled, but the failure/cancel callbacks weren't consistently updating UI state, and there wasn't a single, reliable place that decided "is this order actually paid or not."
How I found it:
I deliberately triggered failure and cancellation cases repeatedly (rather than only testing the happy path) and watched both the browser console and the order state in the database side by side. That made the mismatch between "what the UI shows" and "what the database says" visible.
Fix:
I restructured the payment and retry logic so that:
Payment success is never inferred from the frontend alone — the backend independently verifies payment details before marking an order `PAID`.
Failed or cancelled payments explicitly keep the order in a pending state and surface a "Retry Payment" option tied to the same cart.
I added PostgreSQL persistence for orders, order items, and payments, plus audit logging (e.g. `PAYMENT_CREATED`, `PAYMENT_VERIFIED`, `PAYMENT_FAILED`, `ORDER_PAID`), so the true state of every order is always recoverable from the database rather than from transient frontend state.
What I learned:
For anything touching money, the failure and retry paths need as much design attention as the success path — arguably more, since a customer stuck after a failed payment is a worse outcome than a slightly slower success flow. Treating "is this paid?" as a single server-verified source of truth, rather than something the UI decides, was the fix that mattered most.
---
Net result
After these fixes, the system reliably handles three payment outcomes — successful, failed, and cancelled-with-retry — without ever falsely marking an unpaid order as paid, and every state transition is recorded in the audit log for traceability.