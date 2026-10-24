FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py app_instance.py chart_theme.py callbacks.py charts.py constants.py databook.py engine.py i18n.py layout.py market_data.py ./
COPY assets/ ./assets/

EXPOSE 8052
ENV HOST=0.0.0.0

# Le cache disque (.pea_forecast_cache.pkl, à côté des scripts) évite de retélécharger via yfinance
# à chaque relancement (24 h pour les états financiers, 1 h pour les cours). Pour le faire persister
# entre deux lancements du conteneur :
# docker run -v financial-analysis-cache:/app -p 8052:8052 financial-analysis
CMD ["python", "app.py"]
