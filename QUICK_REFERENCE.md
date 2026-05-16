# Quick Reference - CI/CD Pipeline

## Files We Created/Modified

### New Test Files
```
inventory/tests/test_openapi_contract.py     # 13 contract tests
inventory/tests/test_api_functional.py       # 20+ functional tests
```

### New Workflows
```
.github/workflows/validate-openapi.yml       # Schema validation (NEW)
```

### Updated Workflows
```
.github/workflows/ci.yml                     # Main CI with tests
.github/workflows/deploy-production.yml      # Production deployment with approval
```

### Documentation
```
TESTING_AND_CICD.md                         # Full testing documentation
CICD_IMPLEMENTATION.md                      # Implementation details
DEPLOYMENT_GUIDE.md                         # Step-by-step deployment guide
```

### Backend Code Fix
```
inventory/views.py                          # Multipart form-data fix
```

### Dependencies
```
requirements.txt                            # Added: openapi-spec-validator, jsonschema
pyproject.toml                              # pytest configuration
```

---

## Quick Commands

### Run Tests
```bash
# Contract tests (schema validation)
pytest inventory/tests/test_openapi_contract.py -v

# Functional tests (business logic)
pytest inventory/tests/test_api_functional.py -v

# Critical tests only
pytest -m "p0" -v

# All tests with coverage
pytest inventory/tests/ --cov=inventory --cov-report=html
```

### Deploy to Production
1. Merge PR to main
2. Go to GitHub Actions → Deploy API production
3. Click "Run workflow"
4. Enter image tag
5. Approve when prompted

### Check Deployment Status
```bash
# Health check
curl https://api.affordable-gadgetske.com/health/

# Check schema updated
curl https://api.affordable-gadgetske.com/openapi.yaml
```

---

## Pipeline Flow

```
Code Change
    ↓
Create PR
    ↓
CI runs automatically
├─ Tests run (✓ must pass)
├─ Schema validated (✓ must pass)
├─ Docker built (✓ must succeed)
└─ Coverage uploaded
    ↓
PR approved by reviewer
    ↓
Merge to main
    ↓
Frontend CI regenerates clients
    ↓
Ready for production
    ↓
Manual: Trigger Deploy to Production
    ↓
Approval required (GitHub Environment)
    ↓
Rolling update
    ↓
Smoke tests verify
    ↓
✓ Deployed!
```

---

## Test Priorities

- **P0** - Critical (must pass)
  - Product listing, details
  - Schema compliance
  - 11 tests

- **P1** - High priority (must pass)
  - Articles, permissions
  - File uploads
  - 15+ tests

- **P2** - Standard (should pass)
  - Documentation, optional
  - Can skip for speed

---

## GitHub Setup Needed

### Environment Protection Rule
Settings → Environments → production
- Required reviewers: ✓ Yes
- Dismiss stale: ✓ Yes
- Admin bypass: ☐ No

### Required Secrets
- GCP_WIF_PROVIDER
- GCP_DEPLOY_SA
- GCP_PROJECT_ID
- PRODUCTION_API_MIG_NAME

---

## Common Tasks

### Run Tests Locally
```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest inventory/tests/ -v

# Run specific test
pytest inventory/tests/test_openapi_contract.py::TestOpenAPIContractPublicEndpoints::test_openapi_spec_is_valid -v
```

### Check What Changed
```bash
git status
git diff
```

### Commit and Push
```bash
git add -A
git commit -m "Your message"
git push origin branch-name
```

### Regenerate OpenAPI Schema
```bash
python manage.py spectacular --file openapi.yaml
```

### Validate Schema Locally
```bash
python -c "
import yaml
from openapi_spec_validator import validate_spec
with open('openapi.yaml') as f:
    spec = yaml.safe_load(f)
validate_spec(spec)
print('✓ Valid')
"
```

---

## Deployment Checklist

- [ ] All tests pass on CI
- [ ] Schema validation passes
- [ ] PR approved by reviewer
- [ ] Migration plan reviewed (if DB changes)
- [ ] Rollback plan ready
- [ ] Team notified
- [ ] Deployment triggered manually
- [ ] Environment approval confirmed
- [ ] Smoke tests pass
- [ ] Verify health endpoint
- [ ] Check Sentry for errors

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Tests fail | Check logs, run locally, fix, push |
| Schema fails | Regenerate schema, validate, commit |
| Deployment hangs | Approve in GitHub, check GCP console |
| Need rollback | Go to Actions → Rollback, enter old tag |
| Clients not updated | Frontend CI will auto-generate on next build |

---

## Documentation Files

| File | Purpose |
|------|---------|
| TESTING_AND_CICD.md | Full testing guide, how to run tests |
| CICD_IMPLEMENTATION.md | Implementation details, what was built |
| DEPLOYMENT_GUIDE.md | Step-by-step deployment instructions |
| This file | Quick reference card |

---

## Key Improvements

✓ Automated testing (no more manual testing)
✓ Contract testing (API conforms to schema)
✓ Functional testing (critical flows work)
✓ Manual approval (prevents accidental deployments)
✓ Schema validation (detects breaking changes)
✓ Client generation (frontends always in sync)
✓ Smoke tests (verification after deployment)
✓ Coverage tracking (code quality metrics)
✓ Audit trail (who did what, when)

---

## Need Help?

1. Check the relevant documentation file
2. Look at GitHub Actions logs
3. Run tests locally to debug
4. Check workflow YAML for configuration
5. Review test files for examples

Ready to deploy? 🚀
