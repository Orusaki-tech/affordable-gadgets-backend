# Cloudflare cache rules (API)

Apply in Cloudflare dashboard for `api.affordable-gadgetske.com`:

## Cache public GET catalog (short TTL)

- **URL:** contains `/api/v1/public/products`
- **Methods:** GET
- **Cache TTL:** 60–300s
- **Cache key:** include header `X-Brand-Code`

Also consider:

- `/api/v1/public/promotions/`
- `/api/v1/public/categories/` (if applicable)

## Bypass cache

- `POST`, `PUT`, `PATCH`, `DELETE`
- `/api/auth/`, `/api/inventory/`, cart mutations, checkout, Pesapal IPN
- `/admin/`, `/health/` (optional bypass for accurate health)

## WAF rate limits

- Login: `/api/v1/public/` login paths and admin token login
- Register and review OTP endpoints

## Event day

- Enable Attack Mode if needed
- Purge cache after bulk catalog admin updates
