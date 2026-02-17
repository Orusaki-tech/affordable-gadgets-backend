# Production Deployment Checklist

Use this checklist when deploying to production.

**Note**: This application consists of 3 separate components. For complete deployment guide, see [MULTI_APP_DEPLOYMENT.md](./MULTI_APP_DEPLOYMENT.md).

## Pre-Deployment

- [ ] All code changes committed and pushed
- [ ] `.env.example` created with all required variables
- [ ] Production settings file created (`store/settings_production.py`)
- [ ] Hardcoded secrets removed from codebase
- [ ] Security headers configured
- [ ] CORS settings updated for production
- [ ] `requirements.txt` updated with production dependencies
- [ ] `Procfile` created for Railway/Heroku
- [ ] Next.js config updated for production
- [ ] All migrations tested and ready

## Backend Deployment (Railway/Heroku)

- [ ] PostgreSQL database service added
- [ ] All environment variables set in platform dashboard
- [ ] `DJANGO_ENV=production` set
- [ ] Strong `SECRET_KEY` generated and set
- [ ] `ALLOWED_HOSTS` configured with production domains
- [ ] Database credentials configured
- [ ] Cloudinary credentials configured
- [ ] Pesapal credentials configured (if using)
- [ ] CORS origins set to frontend domain(s)
- [ ] Deployment triggered
- [ ] Migrations run: `python manage.py migrate`
- [ ] Static files collected: `python manage.py collectstatic --noinput`
- [ ] API health check passes
- [ ] Security check passes: `python manage.py check --deploy`

## Frontend Deployment (Vercel)

- [ ] Repository connected to Vercel
- [ ] Root directory set: `frontend_inventory_and_orders/shwari-phones`
- [ ] Build command: `npm run build`
- [ ] All environment variables set:
  - [ ] `NEXT_PUBLIC_API_BASE_URL`
  - [ ] `NEXT_PUBLIC_BRAND_CODE`
  - [ ] `NEXT_PUBLIC_BRAND_NAME`
- [ ] Deployment triggered
- [ ] Build succeeds
- [ ] Production URL accessible

## Post-Deployment Verification

### Backend
- [ ] API endpoints respond correctly
- [ ] Authentication works
- [ ] CORS headers present and correct
- [ ] Database queries work
- [ ] Media uploads work (Cloudinary)
- [ ] Static files serve correctly
- [ ] Security headers present
- [ ] HTTPS enforced
- [ ] No errors in logs

### Frontend
- [ ] Homepage loads
- [ ] Products display correctly
- [ ] Images load from Cloudinary
- [ ] API calls succeed (check browser console)
- [ ] Cart functionality works
- [ ] Checkout flow works
- [ ] No console errors
- [ ] Mobile responsive

## Security Verification

- [ ] `DEBUG=False` in production
- [ ] `SECRET_KEY` is strong and from environment
- [ ] `ALLOWED_HOSTS` restricts to production domains
- [ ] CORS only allows frontend domain
- [ ] HTTPS enforced
- [ ] Secure cookies enabled
- [ ] CSRF protection working
- [ ] Security headers present:
  - [ ] X-Frame-Options: DENY
  - [ ] X-Content-Type-Options: nosniff
  - [ ] Strict-Transport-Security
  - [ ] X-XSS-Protection

## Custom Domains (Optional)

- [ ] Backend custom domain configured
- [ ] Frontend custom domain configured
- [ ] DNS records updated
- [ ] SSL certificates active
- [ ] `ALLOWED_HOSTS` updated with custom domain
- [ ] `CORS_ALLOWED_ORIGINS` updated with custom domain
- [ ] `NEXT_PUBLIC_API_BASE_URL` updated if backend domain changed

## Keep backend warm (Railway)

Railway can put the backend to sleep when idle. The first request after idle (e.g. login) may take 30–60+ seconds or time out. To avoid this:

- [ ] **GitHub Actions keep-warm** (in-repo): `.github/workflows/keep-warm.yml` pings the backend every 5 minutes. Ensure the workflow is enabled; optionally set repo variable `BACKEND_URL` if your production URL differs from the default.
- [ ] **Alternative**: Use an external uptime monitor (e.g. [UptimeRobot](https://uptimerobot.com), [cron-job.org](https://cron-job.org)) to request `https://your-backend.railway.app/health/` or `https://your-backend.railway.app/` every 5–10 minutes.

See [docs/RAILWAY_KEEP_WARM.md](docs/RAILWAY_KEEP_WARM.md) for details.

## Monitoring Setup

- [ ] Error tracking configured (Sentry)
- [ ] Logging configured
- [ ] Uptime monitoring set up
- [ ] Alerts configured
- [ ] Database backup schedule set

## Documentation

- [ ] Deployment process documented
- [ ] Environment variables documented
- [ ] Rollback procedures documented
- [ ] Troubleshooting guide created

