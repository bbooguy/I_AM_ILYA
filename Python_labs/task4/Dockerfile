FROM python:3.13-slim@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 BANK_HOST=0.0.0.0 BANK_DB=/data/bank.sqlite3 BANK_SECRET_DIR=/run/secrets
RUN groupadd --gid 10001 bank && useradd --uid 10001 --gid bank --no-create-home bank \
    && mkdir /app /data && chown bank:bank /app /data
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=bank:bank main.py ./
USER bank
EXPOSE 9999
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 CMD ["python", "-c", "import socket; s=socket.create_connection(('127.0.0.1',9999),2); assert s.recv(64).startswith(b'BANK SERVER READY'); s.close()"]
CMD ["python", "main.py"]
