FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.12-alpine

COPY --from=builder /root/.local /root/.local
COPY exporter.py .

ENV PATH=/root/.local/bin:$PATH

EXPOSE 9877

ENTRYPOINT ["python", "exporter.py"]
