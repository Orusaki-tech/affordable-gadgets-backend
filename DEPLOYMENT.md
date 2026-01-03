# Production Deployment Guide

This guide covers deploying the Affordable Gadgets application to production.

## Prerequisites

- PostgreSQL database (production-ready)
- Cloudinary account for media storage
- Railway/Heroku account for backend hosting
- Vercel account for frontend hosting
- Domain names (optional but recommended)

## Phase 1: Pre-Deployment Preparation

### 1.1 Environment Variables

Copy `.env.example` to `.env` and fill in all required values:

```bash
cp .env.example .env
```

**Critical variables:**
- `SECRET_KEY` - Generate using: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
- `ALLOWED_HOSTS` - Your production domains
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` - PostgreSQL credentials
- `CORS_ALLOWED_ORIGINS` - Your frontend domain(s)
- `CLOUDINARY_*` - Cloudinary credentials
- `PESAPAL_*` - Pesapal payment gateway credentials

### 1.2 Database Migrations

Ensure all migrations are up to date:

```bash
python manage.py makemigrations
python manage.py migrate
```

### 1.3 Static Files

Collect static files:

```bash
python manage.py collectstatic --noinput
```

## Phase 2: Backend Deployment (Railway/Heroku)

### 2.1 Railway Setup

1. Create a new project on Railway
2. Connect your GitHub repository
3. Add PostgreSQL service
4. Configure environment variables in Railway dashboard
5. Set build command: (auto-detected)
6. Set start command: `gunicorn store.wsgi:application --bind 0.0.0.0:$PORT`

### 2.2 Required Environment Variables (Backend)

Set these in Railway/Heroku dashboard:

```
DJANGO_ENV=production
SECRET_KEY=<generate-strong-key>
DEBUG=False
ALLOWED_HOSTS=your-api-domain.railway.app,yourdomain.com
DB_NAME=<from-postgres-service>
DB_USER=<from-postgres-service>
DB_PASSWORD=<from-postgres-service>
DB_HOST=<from-postgres-service>
DB_PORT=5432
# CORS: Include both frontend domains (e-commerce + admin)
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://admin.yourdomain.com,https://www.yourdomain.com
CLOUDINARY_CLOUD_NAME=<your-cloud-name>
CLOUDINARY_API_KEY=<your-api-key>
CLOUDINARY_API_SECRET=<your-api-secret>
PESAPAL_CONSUMER_KEY=<your-consumer-key>
PESAPAL_CONSUMER_SECRET=<your-consumer-secret>
PESAPAL_ENVIRONMENT=live
PESAPAL_CALLBACK_URL=https://yourdomain.com/payment/callback/
PESAPAL_IPN_URL=https://your-api-domain.railway.app/api/inventory/pesapal/ipn/
```

### 2.3 Post-Deployment Commands

After first deployment, run:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

## Phase 3: Frontend Deployment (Vercel)

### 3.1 Vercel Setup

1. Import your GitHub repository
2. Configure project:
   - Framework: Next.js
   - Root directory: `frontend_inventory_and_orders/shwari-phones`
   - Build command: `npm run build`
   - Output directory: `.next`

### 3.2 Required Environment Variables (Frontend)

Set these in Vercel dashboard:

```
NEXT_PUBLIC_API_BASE_URL=https://your-api-domain.railway.app
NEXT_PUBLIC_BRAND_CODE=AFFORDABLE_GADGETS
NEXT_PUBLIC_BRAND_NAME=Affordable Gadgets
NODE_ENV=production
```

### 3.3 Build Configuration

Vercel will automatically:
- Install dependencies (`npm ci`)
- Build the application (`npm run build`)
- Deploy to production

## Phase 4: Post-Deployment Verification

### 4.1 Backend Checks

- [ ] API is accessible at production URL
- [ ] Health check endpoint works
- [ ] Database connections work
- [ ] Static files are served correctly
- [ ] Media uploads work (Cloudinary)
- [ ] CORS headers are correct
- [ ] Security headers are present

### 4.2 Frontend Checks

- [ ] Homepage loads correctly
- [ ] API calls work (check browser console)
- [ ] Images load from Cloudinary
- [ ] Product browsing works
- [ ] Cart functionality works
- [ ] Checkout flow works
- [ ] No console errors

### 4.3 Security Verification

Run Django security check:

```bash
python manage.py check --deploy
```

Verify:
- [ ] HTTPS is enforced
- [ ] Secure cookies are set
- [ ] CSRF protection works
- [ ] Security headers are present
- [ ] No sensitive data in responses

## Phase 5: Custom Domains (Optional)

### 5.1 Backend Domain

1. Add custom domain in Railway/Heroku
2. Update DNS records
3. Update `ALLOWED_HOSTS` environment variable
4. Update `CORS_ALLOWED_ORIGINS` with new domain

### 5.2 Frontend Domain

1. Add custom domain in Vercel
2. Update DNS records
3. SSL certificate is automatically provisioned
4. Update `NEXT_PUBLIC_API_BASE_URL` if backend domain changed

## Phase 6: Monitoring and Maintenance

### 6.1 Error Tracking

Set up error tracking (Sentry recommended):
- Configure Sentry for Django backend
- Configure Sentry for Next.js frontend
- Set up alerts for critical errors

### 6.2 Logging

- Monitor application logs in Railway/Heroku
- Set up log aggregation if needed
- Configure log retention policies

### 6.3 Database Backups

- Set up automated database backups
- Test restore procedures
- Document backup schedule

### 6.4 Updates and Maintenance

**Updating the application:**

1. Make changes in development
2. Test thoroughly
3. Commit and push to repository
4. Railway/Heroku will auto-deploy backend
5. Vercel will auto-deploy frontend
6. Run migrations if needed: `python manage.py migrate`
7. Verify deployment

**Database migrations:**

```bash
# In Railway/Heroku console or via CLI
python manage.py migrate
```

## Troubleshooting

### Backend Issues

**Database connection errors:**
- Verify database credentials
- Check database service is running
- Verify network connectivity

**Static files not loading:**
- Run `python manage.py collectstatic --noinput`
- Check `STATIC_ROOT` configuration
- Verify static files service

**CORS errors:**
- Check `CORS_ALLOWED_ORIGINS` includes frontend domain
- Verify frontend is using HTTPS
- Check browser console for specific CORS error

### Frontend Issues

**API connection errors:**
- Verify `NEXT_PUBLIC_API_BASE_URL` is correct
- Check backend is accessible
- Verify CORS configuration

**Build errors:**
- Check build logs in Vercel
- Verify all environment variables are set
- Check for TypeScript errors

**Image loading issues:**
- Verify Cloudinary credentials
- Check `next.config.ts` image domains
- Verify image URLs in API responses

## Rollback Procedures

### Backend Rollback

1. In Railway/Heroku, revert to previous deployment
2. Or redeploy previous git commit/tag
3. Run migrations if needed

### Frontend Rollback

1. In Vercel, revert to previous deployment
2. Or redeploy previous git commit/tag

## Support

For issues or questions:
- Check application logs
- Review error tracking (Sentry)
- Consult deployment platform documentation

