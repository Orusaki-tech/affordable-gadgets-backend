# Testing & CI/CD Pipeline

This document describes the comprehensive testing and continuous integration/deployment pipeline for Affordable Gadgets backend API.

## Overview

The CI/CD pipeline ensures code quality and API contract compliance before production deployment:

1. **Automated Testing** - Runs on every commit and PR
2. **Contract Testing** - Validates API responses against OpenAPI spec
3. **Schema Validation** - Ensures OpenAPI schema is valid and detects breaking changes
4. **Manual Approval Gate** - Only approved PRs trigger production deployment
5. **Automated Client Generation** - Frontend clients regenerate when schema changes

## Test Suites

### 1. Contract Tests (`test_openapi_contract.py`)

Validates that API responses conform to the OpenAPI specification. This ensures:
- API clients can trust the contract
- Schema changes don't break clients
- All endpoints are properly documented

**Key tests:**
- `TestOpenAPIContractPublicEndpoints` - Validates public endpoint responses
- `TestOpenAPISchemaConsistency` - Ensures schema completeness
- `TestOpenAPIMediaTypes` - Verifies correct content types
- `TestOpenAPIThumbnailImageField` - Validates new `thumbnail_image` field

**Run contract tests:**
```bash
pytest inventory/tests/test_openapi_contract.py -v -m "p0 or p1"
```

### 2. Functional Tests (`test_api_functional.py`)

Tests critical business flows and endpoints based on OpenAPI spec:

**Key test classes:**
- `TestProductListingEndpoint` - Product browsing (storefront)
- `TestProductDetailEndpoint` - Product details
- `TestProductArticleManagement` - Buying guide creation/update
- `TestContentCreatorPermissions` - RBAC and permissions
- `TestMultipartFormDataHandling` - File uploads (thumbnail images)
- `TestCriticalBusinessFlows` - End-to-end flows

**Run functional tests:**
```bash
pytest inventory/tests/test_api_functional.py -v -m "p0 or p1"
```

### 3. Existing Test Suites

Additional comprehensive tests already in place:
- `test_product_content_permissions.py` - Content creator permissions
- `test_rbac_permissions.py` - Role-based access control
- `test_inventory_unit.py` - Inventory management
- `test_order_lifecycle.py` - Order management

## CI/CD Workflows

### Workflow 1: CI (Continuous Integration)

**File:** `.github/workflows/ci.yml`
**Triggers:** Every PR and push to `main`/`master`

**Steps:**
1. Set up PostgreSQL test database
2. Install dependencies
3. Django health check
4. Run database migrations
5. Run functional tests (P0 & P1 priorities)
6. Run contract tests (P0 & P1 priorities)
7. Run full test suite with coverage
8. Build Docker image
9. Upload coverage to Codecov

**Failure:** PR cannot merge if tests fail

### Workflow 2: Validate & Generate OpenAPI Schema

**File:** `.github/workflows/validate-openapi.yml`
**Triggers:** Changes to models, serializers, views, or URLs

**Steps:**
1. Generate schema via `python manage.py spectacular`
2. Validate schema against OpenAPI 3.0 spec
3. Detect breaking changes
4. Comment on PR if schema changed
5. Alert reviewers to regenerate clients

**Purpose:** Ensures schema is always in sync with code

### Workflow 3: Deploy to Production

**File:** `.github/workflows/deploy-production.yml`
**Triggers:** Manual workflow dispatch (`workflow_dispatch`)
**Approval:** Requires `environment: production` protection rules

**Steps:**
1. **Approval Gate** - Requires environment approval
2. **Build & Push** - Build Docker image and push to Artifact Registry
3. **Promote** - Rolling update of production MIG
4. **Smoke Tests** - Health check and schema accessibility
5. **Verification** - Confirm OpenAPI schema endpoint is working

**Protection:** Only manually triggered; requires explicit approval

### Workflow 4: Rollback Production

**File:** `.github/workflows/rollback-production.yml`
**Purpose:** Quick rollback if deployment causes issues

## Test Priorities

Tests are marked with priority levels:

- **P0** - Critical path tests (must pass)
  - Product listing
  - Product details
  - Schema compliance
  
- **P1** - High priority business logic (must pass)
  - Article management
  - Content creator permissions
  - Multipart uploads
  
- **P2** - Standard tests (should pass)
  - Documentation endpoints
  - Optional features

Run tests by priority:
```bash
pytest -m "p0"              # Critical tests only
pytest -m "p0 or p1"       # Critical + high priority
pytest -m "not p2"         # Skip low priority
pytest                      # All tests
```

## Running Tests Locally

### Install test dependencies
```bash
pip install -r requirements.txt
```

### Run all tests
```bash
pytest inventory/tests/ -v
```

### Run with coverage report
```bash
pytest inventory/tests/ --cov=inventory --cov-report=html
open htmlcov/index.html
```

### Run specific test class
```bash
pytest inventory/tests/test_api_functional.py::TestProductListingEndpoint -v
```

### Run contract tests only
```bash
pytest inventory/tests/test_openapi_contract.py -v
```

### Run tests matching pattern
```bash
pytest -k "article" -v
```

## Deployment Process

### For Production Deployment

1. **Create PR** with changes
2. **CI runs automatically** - Tests, schema validation, builds Docker image
3. **Reviewers approve PR** (if changes look good)
4. **Merge PR to main/master**
5. **Manual deployment trigger** - Go to GitHub Actions → Deploy API production
6. **Select image tag** (usually `main` latest commit SHA)
7. **Approval confirmation** - Confirm deployment to production environment
8. **Automated promotion** - Rolling update of production MIG
9. **Smoke tests** - Automatic health checks after deployment

### Deployment Checklist

Before manually triggering production deployment:
- [ ] PR is approved and merged
- [ ] All CI checks passed (tests, schema, build)
- [ ] Migration plan reviewed (if database changes)
- [ ] Rollback plan ready
- [ ] Team notified

## Schema Management

### Regenerating OpenAPI Schema

Schema is auto-generated from Django models and serializers:

```bash
python manage.py spectacular --file openapi.yaml
```

This happens automatically during:
- CI builds (in Docker build)
- Deployment (in `build.sh`)
- Manual generation for local testing

### Schema Versioning

- Schema is committed to repo for reference
- Source of truth is Django code (models + serializers)
- Each deployment updates schema on production API
- CI validates schema is valid OpenAPI 3.0

### Breaking Changes

If PR changes schema:
1. CI workflow detects and comments on PR
2. Reviewers must approve breaking changes
3. API clients must be regenerated
4. Deployment notes should document change

## Client Generation

Frontend apps auto-regenerate API clients when schema changes:

1. **CI detects schema change** in PR
2. **Client generation triggered** via `prebuild` npm script
3. **New clients committed** to frontend repos during their builds
4. **Deployment syncs** latest schema to all apps

See frontend `package.json`:
```json
{
  "scripts": {
    "generate:client": "openapi-generator-cli generate ...",
    "prebuild": "npm run generate:client"
  }
}
```

## Monitoring & Alerts

### Health Checks

- Automatic smoke tests after each deployment
- Periodic health check via cron (see `health-cron.yml`)
- Keep-warm pings to prevent cold starts (see `keep-warm.yml`)

### Coverage Reports

- Coverage uploaded to Codecov after each CI run
- Target coverage: >80%
- Trend tracking via Codecov dashboard

### Production Verification

After production deployment:
1. Check API health: `GET /health/`
2. Check schema: `GET /openapi.yaml`
3. Monitor error rates in Sentry
4. Check response times in metrics

## Troubleshooting

### Tests fail locally but pass in CI

**Cause:** Environment differences (database, secrets, settings)

**Solution:**
```bash
# Set CI environment
export DJANGO_SETTINGS_MODULE=store.settings
export SECRET_KEY=ci-secret-key
export DEBUG=True
export DATABASE_URL=postgresql://user:pass@localhost/test_db

pytest inventory/tests/
```

### Schema validation fails

**Cause:** Invalid OpenAPI 3.0 schema generated

**Solution:**
```bash
# Regenerate schema
python manage.py spectacular --file openapi.yaml

# Validate locally
python -c "
import yaml
from openapi_spec_validator import validate_spec
with open('openapi.yaml') as f:
    spec = yaml.safe_load(f)
validate_spec(spec)
"
```

### Deployment fails with image not found

**Cause:** Image tag doesn't exist in Artifact Registry

**Solution:**
1. Check `deploy-staging.yml` built image successfully
2. Use correct image tag format: `us-central1-docker.pkg.dev/PROJECT/ag-api/ag-api:SHA`
3. Verify artifact registry push completed

## Security Considerations

- **No secrets in tests** - Use fixtures and mocks
- **Environment-based config** - Settings loaded from env vars
- **RBAC testing** - Permissions tested for each role
- **SQL injection protection** - ORM prevents injection
- **CSRF/CORS** - Configured in Django settings

## Performance

- Tests run in parallel where possible
- Database is reused between tests (`--reuse-db`)
- Fixtures are optimized for speed
- CI completes in ~5-10 minutes

## Future Improvements

- [ ] Add performance benchmarks
- [ ] Implement contract testing with generated clients
- [ ] Add load testing to CI
- [ ] Implement canary deployments
- [ ] Add automatic rollback on failed health checks
