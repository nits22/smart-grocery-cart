FROM python:3.11-slim

# system deps for playwright
RUN apt-get update && apt-get install -y curl wget gnupg ca-certificates libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxss1 libasound2 libgbm1 fonts-liberation libx11-6 libxcomposite1 libxdamage1 libxrandr2

WORKDIR /app
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# install playwright browsers
RUN python -m playwright install --with-deps

COPY . /app

ENV PORT=8501
EXPOSE 8501

CMD ["streamlit", "run", "streamlit_real_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
