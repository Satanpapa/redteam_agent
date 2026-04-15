FROM kalilinux/kali-rolling:latest

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv nmap nikto metasploit-framework \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip3 install --break-system-packages --no-cache-dir -r /app/requirements.txt
COPY . /app

ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python3", "-m", "code.cli"]
