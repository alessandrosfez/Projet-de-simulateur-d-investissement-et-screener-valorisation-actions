FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py app_instance.py callbacks.py charts.py constants.py engine.py i18n.py layout.py market_data.py results.py ./

EXPOSE 8050

# Le cache disque (.pea_forecast_cache.pkl, à côté des scripts) évite de retélécharger via yfinance
# à chaque redémarrage tant que les données ont moins d'1h. Pour le faire persister entre deux
# lancements du conteneur : docker run -v pea-cache:/app -p 8050:8050 pea-forecast-dash
CMD ["python", "app.py"]
