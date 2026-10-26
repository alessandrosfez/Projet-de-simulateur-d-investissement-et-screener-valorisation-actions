FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py app_instance.py chart_theme.py charts.py constants.py engine.py i18n.py layout.py market_data.py \
     portfolio_db.py portfolio_engine.py results.py summary_api.py ./
COPY callbacks/ ./callbacks/
COPY assets/ ./assets/

EXPOSE 8050
ENV HOST=0.0.0.0

# Le cache disque (.pea_forecast_cache.pkl) et la base du portefeuille réel (.pea_forecast_portfolio.db),
# toutes deux à côté des scripts, évitent respectivement de retélécharger via yfinance à chaque
# relancement (tant que les données ont moins d'1h) et de perdre les transactions/dividendes saisis.
# Pour les faire persister entre deux lancements du conteneur :
# docker run -v pea-projection-cache:/app -p 8050:8050 pea-portfolio-projection
CMD ["python", "app.py"]
