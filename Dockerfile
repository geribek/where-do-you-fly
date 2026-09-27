FROM python:3.12-slim-bookworm
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home flight
COPY backend/flight_display ./backend/flight_display
COPY calibration ./calibration
COPY fixtures ./fixtures
ENV PYTHONPATH=/app/backend PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 10001:10001
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('APP_PORT','8001')+'/healthz',timeout=2)"
CMD ["python", "-m", "flight_display.run"]
