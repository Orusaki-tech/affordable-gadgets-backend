## Description

<!-- Briefly describe the purpose of this PR -->

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Refactor / code style
- [ ] Documentation
- [ ] CI / CD
- [ ] Database migration
- [ ] Dependency update

## Checklist

- [ ] All CI checks pass (tests, lint, schema validation)
- [ ] Added/updated tests for the change
- [ ] Ran full test suite locally: `pytest inventory/tests/ -v`
- [ ] OpenAPI schema regenerated (if models/serializers/views changed):
      `python manage.py spectacular --file openapi.yaml`
- [ ] Schema validated: `pytest inventory/tests/test_openapi_contract.py -v`
- [ ] No breaking API changes (or documented and approved)
- [ ] Frontend repos notified if schema changed (clients must be regenerated)
- [ ] Migration plan reviewed (if DB changes)
- [ ] Rollback plan ready

## Related Issues

<!-- Link any related issues -->

## Testing Notes

<!-- Describe how you tested the changes -->

## Deployment Notes

<!-- Any special deployment steps, env vars, or secrets to configure -->