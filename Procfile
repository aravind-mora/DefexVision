# Production processes (used by Render / Railway / Heroku)
# web       = Django app served by gunicorn
# inference = Flask inference API served by gunicorn on another port
web: gunicorn defexvision.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120
inference: gunicorn "inference_api.wsgi:app" --bind 0.0.0.0:5001 --workers 1 --timeout 120
