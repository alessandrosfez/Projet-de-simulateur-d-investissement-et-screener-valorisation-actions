FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py app_instance.py callbacks.py charts.py constants.py engine.py i18n.py layout.py market_data.py results.py ./
COPY assets/ ./assets/

EXPOSE 8050
ENV HOST=0.0.0.0

# Le cache disque (.pea_forecast_cache.pkl, à côté des scripts) évite de retélécharger via yfinance
# à chaque relancement tant que les données ont moins d'1h. Pour le faire persister entre deux
# lancements du conteneur : docker run -v pea-projection-cache:/app -p 8050:8050 pea-portfolio-projection
CMD ["python", "app.py"]
