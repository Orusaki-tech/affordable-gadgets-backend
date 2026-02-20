web: sh -c "python manage.py migrate && gunicorn store.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120"

